from datetime import datetime, timedelta
from typing import List, Tuple

from urllib.parse import parse_qs, urlsplit
from fhirclient.models.careplan import CarePlan
from fhirclient.models.communication import Communication
from fhirclient.models.communicationrequest import CommunicationRequest
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.identifier import Identifier
from fhirclient.models.patient import Patient
from fhirclient.models.extension import Extension
from fhirclient.models.practitioner import Practitioner
from flask import current_app

import isacc_messaging
from isacc_messaging.api.email_notifications import send_message_received_notification
from isacc_messaging.api.fhir import HAPI_request
from isacc_messaging.api.ml_utils import predict_score


class IsaccFhirException(Exception):
    """Raised when a FHIR resource or attribute required for ISACC to operate correctly is missing"""
    pass


class IsaccTwilioError(Exception):
    """Raised when Twilio SMS are not functioning as required for ISACC"""
    pass


def first_in_bundle(bundle):
    if bundle['resourceType'] == 'Bundle' and bundle['total'] > 0:
        return bundle['entry'][0]['resource']


class IsaccRecordCreator:
    def __init__(self):
        pass

    def __create_communication_from_request(self, cr):
        if cr.category[0].coding[0].code == 'isacc-manually-sent-message':
            code = 'isacc-manually-sent-message'
        else:
            code = "isacc-auto-sent-message"
        return {
            "resourceType": "Communication",
            "basedOn": [{"reference": f"CommunicationRequest/{cr.id}"}],
            "partOf": [{"reference": f"{cr.basedOn[0].reference}"}],
            "category": [{
                "coding": [{
                    "system": "https://isacc.app/CodeSystem/communication-type",
                    "code": code
                }]
            }],

            "payload": [p.as_json() for p in cr.payload],
            "sent": datetime.now().astimezone().isoformat(),
            "sender": cr.sender.as_json() if cr.sender else None,
            "recipient": [r.as_json() for r in cr.recipient],
            "medium": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/ValueSet/v3-ParticipationMode",
                    "code": "SMSWRIT"
                }]
            }],
            "note": [n.as_json() for n in cr.note] if cr.note else None,
            "status": "completed"
        }

    def convert_communicationrequest_to_communication(self, cr_id=None, cr=None):
        if cr is None and cr_id is not None:
            cr = HAPI_request('GET', 'CommunicationRequest', cr_id)
        if cr is None:
            raise IsaccFhirException("No CommunicationRequest")

        cr = CommunicationRequest(cr)
        if cr.identifier and len([i for i in cr.identifier if i.system == "http://isacc.app/twilio-message-sid"]) > 0:
            twilio_messages = [i.value for i in cr.identifier if i.system == "http://isacc.app/twilio-message-sid"]
            isacc_messaging.audit.audit_entry(
                f"CommunicationRequest already has Twilio SID ",
                extra={
                    'CommunicationRequest': cr.id,
                    "Twilio messages": twilio_messages
                },
                level='debug'
            )
            return None

        target_phone = self.get_caring_contacts_phone_number(cr.recipient[0].reference.split('/')[1])
        result = self.send_twilio_sms(message=cr.payload[0].contentString, to_phone=target_phone)

        if result.status != 'sent' and result.status != 'queued':
            isacc_messaging.audit.audit_entry(
                f"Twilio error",
                extra={"resource": result},
                level='error'
            )
            raise IsaccTwilioError(f"ERROR! Message status is neither sent nor queued. It was {result.status}")
        else:
            if not cr.identifier:
                cr.identifier = []
            cr.identifier.append(Identifier({
                "system": "http://isacc.app/twilio-message-sid",
                "value": result.sid,
                "extension": [{"url": "http://isacc.app/twilio-message-status", "valueCode": result.status}]
            }))
            updated_cr = HAPI_request('PUT', 'CommunicationRequest', resource_id=cr.id, resource=cr.as_json())
            isacc_messaging.audit.audit_entry(
                f"Updated CommunicationRequest with Twilio SID:",
                extra={"resource": updated_cr},
                level='debug'
            )

            return updated_cr

    def send_twilio_sms(self, message, to_phone, from_phone=None):
        from twilio.rest import Client
        account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
        auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
        if from_phone is None:
            from_phone = current_app.config.get('TWILIO_PHONE_NUMBER')

        webhook_callback = current_app.config.get('TWILIO_WEBHOOK_CALLBACK')

        client = Client(account_sid, auth_token)

        message = client.messages.create(
            body=message,
            from_=from_phone,
            to=to_phone,
            status_callback=webhook_callback + '/MessageStatus'
            # ,media_url=['https://demo.twilio.com/owl.png']
        )
        isacc_messaging.audit.audit_entry(
            f"Twilio message created via API",
            extra={"twilio_message": message},
            level='debug'
        )
        return message

    def get_careplan(self, patient_id) -> CarePlan:
        result = HAPI_request(
            'GET', 'CarePlan',
            params={
                "subject": f"Patient/{patient_id}",
                "category": "isacc-message-plan",
                "status": "active",
                "_sort": "-_lastUpdated"})

        result = first_in_bundle(result)
        if result is not None:
            return CarePlan(result)

    def get_patient(self, patient_id):
        result = HAPI_request('GET', 'Patient', resource_id=patient_id)
        if result is not None:
            return Patient(result)

    def get_general_practitioner_emails(self, pt: Patient) -> list:
        emails = []
        if pt and pt.generalPractitioner:
            for gp_ref in pt.generalPractitioner:
                # format of gp_ref.reference: "Practitioner/2"
                resource_type, resource_id = gp_ref.reference.split('/')
                result = HAPI_request('GET', resource_type, resource_id)
                if result is not None:
                    if resource_type != 'Practitioner':
                        raise ValueError(f"expected Practitioner in {gp_ref.reference}")
                    gp = Practitioner(result)
                    for t in gp.telecom:
                        if t.system == 'email':
                            emails.append(t.value)
        if not emails:
            isacc_messaging.audit.audit_entry(
                "no practioner email to notify",
                extra={"Patient": str(pt)},
                level='warn'
            )
        return emails

    def get_caring_contacts_phone_number(self, patient_id):
        pt = self.get_patient(patient_id)
        if pt.telecom:
            for t in pt.telecom:
                if t.system == 'sms':
                    return t.value
        raise IsaccFhirException(f"Error: Patient/{pt.id} doesn't have an sms contact point on file")

    def generate_incoming_message(self, message, time: datetime = None, patient_id=None, priority=None, themes=None,
                                  twilio_sid=None):
        if priority and priority not in ("routine", "urgent", "stat"):
            return f"Invalid priority given: {priority}. Only routine, urgent, and stat are allowed."

        if priority is None:
            priority = "routine"

        if patient_id is None:
            return "Need patient ID"

        care_plan = self.get_careplan(patient_id)

        if not care_plan:
            error = "No CarePlan for this patient:"
            isacc_messaging.audit.audit_entry(
                error,
                extra={"patient ID": patient_id},
                level='error'
            )
            return f"{error}: Patient/{patient_id}"

        if time is None:
            time = datetime.now()

        if themes is None:
            themes = []

        message_time = time.astimezone().isoformat()
        m = {
            'resourceType': 'Communication',
            'identifier': [{"system": "http://isacc.app/twilio-message-sid", "value": twilio_sid}],
            'partOf': [{'reference': f'CarePlan/{care_plan.id}'}],
            'status': 'completed',
            'category': [{'coding': [{'system': 'https://isacc.app/CodeSystem/communication-type',
                                      'code': 'isacc-received-message'}]}],
            'medium': [{'coding': [{'system': 'http://terminology.hl7.org/ValueSet/v3-ParticipationMode',
                                    'code': 'SMSWRIT'}]}],
            'sent': message_time,
            'sender': {'reference': f'Patient/{patient_id}'},
            'payload': [{'contentString': message}],
            'priority': priority,
            'extension': [
                {"url": "isacc.app/message-theme", 'valueString': t} for t in themes
            ]
        }
        c = Communication(m)
        result = HAPI_request('POST', 'Communication', resource=c.as_json())
        isacc_messaging.audit.audit_entry(
            f"Created Communication resource for incoming text",
            extra={"resource": result},
            level='debug'
        )
        patient = self.get_patient(patient_id)
        notify_emails = self.get_general_practitioner_emails(patient)
        patient_name = " ".join([f"{' '.join(n.given)} {n.family}" for n in patient.name])
        send_message_received_notification(notify_emails, message, patient_name)
        self.update_followup_extension(patient_id, message_time)

    def on_twilio_message_status_update(self, values):
        message_sid = values.get('MessageSid', None)
        message_status = values.get('MessageStatus', None)

        cr = HAPI_request('GET', 'CommunicationRequest', params={
            "identifier": f"http://isacc.app/twilio-message-sid|{message_sid}"
        })
        cr = first_in_bundle(cr)
        if cr is None:
            error = "No CommunicationRequest for this Twilio SID"
            isacc_messaging.audit.audit_entry(
                error,
                extra={"message_sid": message_sid},
                level='error'
            )
            return f"{error}: {message_sid}"

        cr = CommunicationRequest(cr)

        # update the message status in the identifier/extension attributes
        for i in cr.identifier:
            if i.system == "http://isacc.app/twilio-message-sid" and i.value == message_sid:
                for e in i.extension:
                    if e.url == "http://isacc.app/twilio-message-status":
                        e.valueCode = message_status

        # sometimes we go straight to delivered. other times we go to sent and then delivered. sometimes we go to sent
        # and never delivered (it has been delivered but we don't get a callback with that status)
        if message_status == 'sent' or message_status == 'delivered':
            existing_comm = first_in_bundle(HAPI_request('GET', 'Communication', params={
                'based-on': f"CommunicationRequest/{cr.id}"
            }))
            if existing_comm is None:
                c = self.__create_communication_from_request(cr)
                c = Communication(c)

                new_c = HAPI_request('POST', 'Communication', resource=c.as_json())
                isacc_messaging.audit.audit_entry(
                    f"Created Communication resource:",
                    extra={"resource": new_c},
                    level='debug'
                )
                # if this was a manual message, mark patient as having been followed up with
                if self.is_manual_follow_up_message(c):
                    self.mark_patient_followed_up(patient_id=cr.recipient[0].reference.split('/')[1])
            else:
                isacc_messaging.audit.audit_entry(
                    f"Received /MessageStatus callback with status {message_status} on existing Communication resource",
                    extra={"resource": existing_comm,
                           "existing status": existing_comm.get('status'),
                           "message status": message_status},
                    level='debug'
                )

            cr.status = "completed"
            cr = HAPI_request('PUT', 'CommunicationRequest', resource_id=cr.id, resource=cr.as_json())

            isacc_messaging.audit.audit_entry(
                f"Updated CommunicationRequest due to twilio status update:",
                extra={"resource": cr},
                level='debug'
            )

    def mark_patient_followed_up(self, patient_id):
        self.update_followup_extension(patient_id=patient_id, value_date_time=None)

    def update_followup_extension(self, patient_id, value_date_time):
        """Keep a single extension on the patient at all times

        The value of the extension is:
        - 50 years in the future for clean sort order, if value passed is None
        - the oldest value_date_time found in the extension if called with a value

        :param patient_id: the patient to mark with the extension
        :param value_date_time: time of incoming message from patient, used to track
          how long it has been since patient reached out.  use None if sending a
          response to the patient.
        """
        patient = self.get_patient(patient_id)
        followup_system = "http://isacc.app/time-of-last-unfollowedup-message"
        if patient.extension is None:
            patient.extension = []

        matching_extensions = [i for i in patient.extension if i.url == followup_system]
        patient.extension = [i for i in patient.extension if i.url != followup_system]

        if value_date_time is None:
            # Set to 50 years in the future for patient sort by functionality
            save_value = FHIRDate((datetime.now().astimezone() + timedelta(days=50*365.25)).isoformat())
        else:
            # If older value exists, prefer
            given_value = FHIRDate(value_date_time)
            existing = [i.valueDateTime for i in matching_extensions]
            save_value = min(given_value, *existing, key=lambda x: x.date) if existing else given_value
        patient.extension.append(Extension({
                "url": followup_system,
                "valueDateTime": save_value.isostring
            }))

        result = HAPI_request('PUT', 'Patient', resource_id=patient_id, resource=patient.as_json())
        isacc_messaging.audit.audit_entry(
            f"Updated Patient resource, last-unfollowedup extension",
            extra={"resource": result},
            level='debug'
        )

    def on_twilio_message_received(self, values):
        pt = HAPI_request('GET', 'Patient', params={
            'telecom': values.get('From').replace("+1", "")
        })
        pt = first_in_bundle(pt)
        if not pt:
            error = "No patient with this phone number"
            phone = values.get('From')
            isacc_messaging.audit.audit_entry(
                error,
                extra={"from_phone": phone},
                level='error'
            )
            return f"{error}: {phone}"
        pt = Patient(pt)

        message = values.get("Body")
        message_priority = self.score_message(message)

        return self.generate_incoming_message(
            message=message,
            time=datetime.now(),
            twilio_sid=values.get('SmsSid'),
            patient_id=pt.id,
            priority=message_priority
        )

    def score_message(self, message):
        model_path = current_app.config.get('TORCH_MODEL_PATH')
        if not model_path:
            return "routine"

        try:
            score = predict_score(message, model_path)
            if score == 1:
                return "stat"
        except Exception as e:
            isacc_messaging.audit.audit_entry(
                "Failed to assess message urgency",
                extra={"exception": e},
                level='error'
            )
        return "routine"

    def execute_requests(self) -> Tuple[List[str], List[dict]]:
        """
        For all due CommunicationRequests, generate SMS, create Communication resource, and update CommunicationRequest
        """
        successes = []
        errors = []

        limit = 200
        result = HAPI_request('GET', 'CommunicationRequest', params={
            "category": "isacc-scheduled-message,isacc-manually-sent-message",
            "status": "active",
            "occurrence": f"le{datetime.now().astimezone().isoformat()}",
            "_count": str(limit)
        })

        self.process_bundle(errors, result, successes)

        if result["total"] > limit:
            while len([link['url'] for link in result["link"] if link['relation'] == 'next']) > 0:
                next_page_url = [link['url'] for link in result["link"] if link['relation'] == 'next'][0]
                next_page_url = urlsplit(next_page_url)
                params = parse_qs(next_page_url.query)
                result = HAPI_request('GET', '', params=params)
                self.process_bundle(errors, result, successes)

        return successes, errors

    def process_bundle(self, errors, result, successes):
        if result['resourceType'] == 'Bundle' and result['total'] > 0:
            for entry in result['entry']:
                cr = entry['resource']
                try:
                    self.convert_communicationrequest_to_communication(cr=cr)
                    successes.append(cr['id'])
                except Exception as e:
                    errors.append({'id': cr['id'], 'error': e})

    def is_manual_follow_up_message(self, c: Communication) -> bool:
        for category in c.category:
            for coding in category.coding:
                if coding.system == 'https://isacc.app/CodeSystem/communication-type':
                    if coding.code == 'isacc-manually-sent-message':
                        return True
        return False
