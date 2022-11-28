from datetime import datetime
from typing import List, Tuple

from fhirclient.models.careplan import CarePlan
from fhirclient.models.communication import Communication
from fhirclient.models.communicationrequest import CommunicationRequest
from fhirclient.models.identifier import Identifier
from fhirclient.models.patient import Patient
from flask import current_app

import isacc_messaging
from isacc_messaging.api.fhir import HAPI_request


class IsaccFhirException(Exception):
    """Raised when a FHIR resource or attribute required for ISACC to operate correctly is missing"""
    pass


class IsaccTwilioError(Exception):
    """Raised when Twilio SMS are not functioning as required for ISACC"""
    pass


def first_in_bundle(bundle):
    if bundle['resourceType'] == 'Bundle' and bundle['total'] > 0:
        return bundle['entry'][0]['resource']
    return None


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
            "recipient": [r.as_json() for r in cr.recipient],
            "medium": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/ValueSet/v3-ParticipationMode",
                    "code": "SMSWRIT"
                }]
            }],
            "status": "completed"
        }

    def convert_communicationrequest_to_communication(self, cr_id=None, cr=None):
        if cr is None and cr_id is not None:
            cr = HAPI_request('GET', 'CommunicationRequest', cr_id)
        if cr is None:
            raise IsaccFhirException("No CommunicationRequest")

        cr = CommunicationRequest(cr)
        if cr.identifier and len([i for i in cr.identifier if i.system == "http://isacc.app/twilio-message-sid"]) > 0:
            twilio_messages = [i for i in cr.identifier if i.system == "http://isacc.app/twilio-message-sid"]
            isacc_messaging.audit.audit_entry(
                f"CommunicationRequest already has Twilio SID ",
                extra={
                    'CommunicationRequest': cr.id,
                    "Twilio messages": twilio_messages
                },
                level='info'
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
                level='info'
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
            level='info'
        )
        return message

    def get_careplan(self, patient_id):
        result = HAPI_request('GET', 'CarePlan', params={"subject": f"Patient/{patient_id}",
                                                         "category": "isacc-message-plan",
                                                         "status": "active",
                                                         "_sort": "-_lastUpdated"})
        result = first_in_bundle(result)
        if result is not None:
            return CarePlan(result)
        else:
            return None

    def get_caring_contacts_phone_number(self, patient_id):
        pt = HAPI_request('GET', 'Patient', patient_id)
        pt = Patient(pt)
        if pt.telecom:
            for t in pt.telecom:
                if t.system == 'sms':
                    return t.value
        raise IsaccFhirException(f"Error: Patient/{pt.id} doesn't have an sms contact point on file")

    def generate_incoming_message(self, message, time: datetime = None, patient_id=None, priority=None, themes=None,
                                  twilio_sid=None):
        if priority is not None and priority != "routine" and priority != "urgent" and priority != "stat":
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

        m = {
            'resourceType': 'Communication',
            'identifier': [{"system": "http://isacc.app/twilio-message-sid", "value": twilio_sid}],
            'partOf': [{'reference': f'CarePlan/{care_plan.id}'}],
            'status': 'completed',
            'category': [{'coding': [{'system': 'https://isacc.app/CodeSystem/communication-type',
                                      'code': 'isacc-received-message'}]}],
            'medium': [{'coding': [{'system': 'http://terminology.hl7.org/ValueSet/v3-ParticipationMode',
                                    'code': 'SMSWRIT'}]}],
            'sent': time.astimezone().isoformat(),
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
            level='info'
        )

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
                    level='info'
                )
            else:
                isacc_messaging.audit.audit_entry(
                    f"Received /MessageStatus callback with status {message_status} but Communication resource already "
                    f"exists:",
                    extra={"resource": existing_comm},
                    level='info'
                )

            cr.status = "completed"

            cr = HAPI_request('PUT', 'CommunicationRequest', resource_id=cr.id, resource=cr.as_json())

            isacc_messaging.audit.audit_entry(
                f"Updated CommunicationRequest due to twilio status update:",
                extra={"resource": cr},
                level='info'
            )

        return None

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
                extras={"from_phone": phone},
                level='error'
            )
            return f"{error}: {phone}"
        pt = Patient(pt)

        return self.generate_incoming_message(
            message=values.get("Body"),
            time=datetime.now(),
            twilio_sid=values.get('SmsSid'),
            patient_id=pt.id
        )

    def execute_requests(self) -> Tuple[List[str], List[dict]]:
        """
        For all due CommunicationRequests, generate SMS, create Communication resource, and update CommunicationRequest
        """
        result = HAPI_request('GET', 'CommunicationRequest', params={
            "category": "isacc-scheduled-message,isacc-manually-sent-message",
            "status": "active",
            "occurrence": f"le{datetime.now().astimezone().isoformat()}"
        })

        successes = []
        errors = []
        if result['resourceType'] == 'Bundle' and result['total'] > 0:
            for entry in result['entry']:
                cr = entry['resource']
                try:
                    self.convert_communicationrequest_to_communication(cr=cr)
                    successes.append(cr['id'])
                except Exception as e:
                    errors.append({'id': cr['id'], 'error': e})
        return successes, errors
