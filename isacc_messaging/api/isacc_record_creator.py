from datetime import datetime, timedelta
import re
from typing import List, Tuple

from fhirclient.models.careplan import CarePlan
from fhirclient.models.communication import Communication
from fhirclient.models.communicationrequest import CommunicationRequest
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.identifier import Identifier
from fhirclient.models.patient import Patient
from fhirclient.models.practitioner import Practitioner
from fhirclient.models.extension import Extension
from flask import current_app
from twilio.base.exceptions import TwilioRestException

import isacc_messaging
from isacc_messaging.api.email_notifications import send_message_received_notification
from isacc_messaging.api.fhir import (
    HAPI_request,
    first_in_bundle,
    next_in_bundle,
    resolve_reference,
)
from isacc_messaging.api.ml_utils import predict_score


def expand_template_args(content: str, patient: Patient, practitioner: Practitioner) -> str:
    """Interpolate any template args (i.e. {name}) in content"""
    def preferred_name(resource, default=None):
        # prefer given name with use category "usual"
        if not resource:
            return default

        for name in resource.name:
            if name.use == "usual":
                # UI cleared preferred names lose `given`
                value = name.given and name.given[0]
                if value:
                    return value

        return resource.name[0].given[0]

    def case_insensitive_replace(text, old, new):
        pattern = re.escape(old)
        return re.sub(pattern, new, text, flags=re.IGNORECASE)

    c = case_insensitive_replace(content, "{name}", preferred_name(patient))
    c = case_insensitive_replace(c, "{username}", preferred_name(practitioner, "Caring Contacts Team"))
    return c


class IsaccFhirException(Exception):
    """Raised when a FHIR resource or attribute required for ISACC to operate correctly is missing"""
    pass


class IsaccTwilioError(Exception):
    """Raised when Twilio SMS are not functioning as required for ISACC"""
    pass


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

    def convert_communicationrequest_to_communication(self, cr):
        if cr.identifier and len([i for i in cr.identifier if i.system == "http://isacc.app/twilio-message-sid"]) > 0:
            sid = ""
            status = ""
            as_of = ""
            for i in cr.identifier:
                for e in i.extension:
                    if e.url == "http://isacc.app/twilio-message-status":
                        status = e.valueCode
                    if e.url == "http://isacc.app/twilio-message-status-updated":
                        as_of = e.valueDateTime.isostring
                if i.system == "http://isacc.app/twilio-message-sid":
                    sid = i.value
            return f"Twilio message (sid: {sid}, CR.id: {cr.id}) was previously dispatched. Last known status: {status} (as of {as_of})"

        target_phone = self.get_caring_contacts_phone_number(resolve_reference(cr.recipient[0].reference))
        try:
            patient=resolve_reference(cr.recipient[0].reference)
            practitioner=self.get_general_practitioner(patient)
            expanded_payload = expand_template_args(
                content=cr.payload[0].contentString,
                patient=patient,
                practitioner=practitioner)
            result = self.send_twilio_sms(message=expanded_payload, to_phone=target_phone)
        except TwilioRestException as ex:
            isacc_messaging.audit.audit_entry(
                "Twilio exception",
                extra={"resource": f"CommunicationResource/{cr.id}", "exception": ex},
                level='exception'
            )
            raise IsaccTwilioError(f"ERROR! {ex} raised attempting to send SMS")

        if result.status != 'sent' and result.status != 'queued':
            isacc_messaging.audit.audit_entry(
                f"Twilio error",
                extra={"resource": result},
                level='error'
            )
            raise IsaccTwilioError(f"ERROR! Message status is neither sent nor queued. It was {result.status}")
        else:
            cr.payload[0].contentString = expanded_payload
            if not cr.identifier:
                cr.identifier = []
            cr.identifier.append(Identifier({
                "system": "http://isacc.app/twilio-message-sid",
                "value": result.sid,
                "extension": [
                    {
                        "url": "http://isacc.app/twilio-message-status",
                        "valueCode": result.status
                    },
                    {
                        "url": "http://isacc.app/twilio-message-status-updated",
                        "valueDateTime": datetime.now().astimezone().isoformat()
                    },
                ]
            }))
            updated_cr = HAPI_request('PUT', 'CommunicationRequest', resource_id=cr.id, resource=cr.as_json())
            isacc_messaging.audit.audit_entry(
                f"Updated CommunicationRequest with Twilio SID:",
                extra={"resource": updated_cr},
                level='debug'
            )

            return f"Twilio message dispatched (status={result.status})"

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

    def get_careplan(self, patient: Patient) -> CarePlan:
        result = HAPI_request(
            'GET', 'CarePlan',
            params={
                "subject": f"Patient/{patient.id}",
                "category": "isacc-message-plan",
                "status": "active",
                "_sort": "-_lastUpdated"})

        result = first_in_bundle(result)
        if result is not None:
            return CarePlan(result)

    def get_care_team_emails(self, patient: Patient) -> list:
        emails = []
        care_plan = self.get_careplan(patient)
        if care_plan and care_plan.careTeam and len(care_plan.careTeam) > 0:
            if len(care_plan.careTeam) > 1:
                isacc_messaging.audit.audit_entry(
                    "patient has more than one care team",
                    extra={"Patient": patient.id},
                    level='warn'
                )
            # get the referenced CareTeam resource from the care plan
            # please see https://www.pivotaltracker.com/story/show/185407795
            # carePlan.careTeam now includes those that follow the patient
            care_team = resolve_reference(care_plan.careTeam[0].reference)
            if care_team and care_team.participant:
                # format of participants: [{member: {reference: Practitioner/1}}]
                for participant in care_team.participant:
                    gp = resolve_reference(participant.member.reference)
                    if gp.resource_type != 'Practitioner':
                        continue
                    for t in gp.telecom:
                        if t.system == 'email':
                            emails.append(t.value)

        if not emails:
            isacc_messaging.audit.audit_entry(
                "no practitioner email to notify",
                extra={"Patient": patient.id},
                level='warn'
            )
        return emails

    def get_general_practitioner(self, pt: Patient) -> Practitioner:
        """return first general practitioner found on patient"""
        if pt and pt.generalPractitioner:
            for gp_ref in pt.generalPractitioner:
                gp = resolve_reference(gp_ref.reference)
                return gp

    def get_general_practitioner_emails(self, pt: Patient) -> list:
        emails = []
        if pt and pt.generalPractitioner:
            for gp_ref in pt.generalPractitioner:
                gp = resolve_reference(gp_ref.reference)
                for t in gp.telecom:
                    if t.system == 'email':
                        emails.append(t.value)
        if not emails:
            isacc_messaging.audit.audit_entry(
                "no practitioner email to notify",
                extra={"Patient": str(pt)},
                level='warn'
            )
        return emails

    def get_caring_contacts_phone_number(self, pt: Patient) -> str:
        if pt.telecom:
            for t in pt.telecom:
                if t.system == 'sms':
                    return t.value
        raise IsaccFhirException(f"Error: Patient/{pt.id} doesn't have an sms contact point on file")

    def generate_incoming_message(self, message, time: datetime = None, patient: Patient=None, priority=None, themes=None,
                                  twilio_sid=None):
        if priority and priority not in ("routine", "urgent", "stat"):
            return f"Invalid priority given: {priority}. Only routine, urgent, and stat are allowed."

        if priority is None:
            priority = "routine"

        if patient is None:
            return "Need patient"

        care_plan = self.get_careplan(patient)

        if not care_plan:
            error = "No CarePlan for this patient:"
            isacc_messaging.audit.audit_entry(
                error,
                extra={"patient ID": patient.id},
                level='error'
            )
            return f"{error}: Patient/{patient.id}"

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
            'sender': {'reference': f'Patient/{patient.id}'},
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
        # look for participating practitioners in patient's care team
        care_team_emails = self.get_care_team_emails(patient)
        # look for practitioners in patient's generalPractitioner field
        practitioners_emails = self.get_general_practitioner_emails(patient)
        # unique email list
        notify_emails = list(set(care_team_emails + practitioners_emails))
        send_message_received_notification(notify_emails, patient)
        self.update_followup_extension(patient, message_time)

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
                    if e.url == "http://isacc.app/twilio-message-status-updated":
                        e.valueDateTime = FHIRDate(datetime.now().astimezone().isoformat())

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
                    self.mark_patient_followed_up(resolve_reference(cr.recipient[0].reference))
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

    def mark_patient_followed_up(self, patient: Patient):
        self.update_followup_extension(patient=patient, value_date_time=None)

    def update_followup_extension(self, patient, value_date_time):
        """Keep a single extension on the patient at all times

        The value of the extension is:
        - 50 years in the future for clean sort order, if value passed is None
        - the oldest value_date_time found in the extension if called with a value

        :param patient: the patient to mark with the extension
        :param value_date_time: time of incoming message from patient, used to track
          how long it has been since patient reached out.  use None if sending a
          response to the patient.
        """
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

        result = HAPI_request('PUT', 'Patient', resource_id=patient.id, resource=patient.as_json())
        isacc_messaging.audit.audit_entry(
            f"Updated Patient resource, last-unfollowedup extension",
            extra={"resource": result},
            level='debug'
        )

    def on_twilio_message_received(self, values):
        pt = HAPI_request('GET', 'Patient', params={
            'telecom': values.get('From', "+1").replace("+1", "")
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
            patient=pt,
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

    def execute_requests(self) -> Tuple[List[dict], List[dict]]:
        """
        For all due CommunicationRequests, generate SMS, create Communication resource, and update CommunicationRequest
        """
        successes = []
        errors = []

        now = datetime.now()
        cutoff = now - timedelta(days=2)

        result = HAPI_request('GET', 'CommunicationRequest', params={
            "category": "isacc-scheduled-message,isacc-manually-sent-message",
            "status": "active",
            "occurrence": f"le{now.astimezone().isoformat()}",
        })

        for cr_json in next_in_bundle(result):
            cr = CommunicationRequest(cr_json)
            if cr.occurrenceDateTime.date < cutoff:
                # skip over any messages more than 48 hours old, as per #186175825
                continue
            self.process_cr(errors, cr, successes)

        return successes, errors

    def process_cr(self, errors, cr, successes):
        try:
            status = self.convert_communicationrequest_to_communication(cr=cr)
            successes.append({'id': cr.id, 'status': status})
        except Exception as e:
            errors.append({'id': cr.id, 'error': e})

    def is_manual_follow_up_message(self, c: Communication) -> bool:
        for category in c.category:
            for coding in category.coding:
                if coding.system == 'https://isacc.app/CodeSystem/communication-type':
                    if coding.code == 'isacc-manually-sent-message':
                        return True
        return False
