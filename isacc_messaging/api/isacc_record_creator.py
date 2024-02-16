from datetime import datetime, timedelta
import re
from typing import List, Tuple

from fhirclient.models.communication import Communication
from flask import current_app
from twilio.base.exceptions import TwilioRestException

from isacc_messaging.api.email_notifications import send_message_received_notification
from isacc_messaging.api.ml_utils import predict_score
from isacc_messaging.audit import audit_entry
from isacc_messaging.models.fhir import (
    HAPI_request,
    first_in_bundle,
    next_in_bundle,
    resolve_reference,
)
from isacc_messaging.models.isacc_communication import IsaccCommunication as Communication
from isacc_messaging.models.isacc_communicationrequest import IsaccCommunicationRequest as CommunicationRequest
from isacc_messaging.models.isacc_fhirdate import IsaccFHIRDate as FHIRDate
from isacc_messaging.models.isacc_patient import IsaccPatient as Patient
from isacc_messaging.models.isacc_practitioner import IsaccPractitioner as Practitioner


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


class IsaccTwilioError(Exception):
    """Raised when Twilio SMS are not functioning as required for ISACC"""
    pass


class IsaccRecordCreator:
    def __init__(self):
        pass

    def dispatch_cr(self, cr: CommunicationRequest):
        if cr.dispatched():
            return cr.dispatched_message_status()

        target_phone = resolve_reference(cr.recipient[0].reference).get_phone_number()
        patient = resolve_reference(cr.recipient[0].reference)
        # Create a new Communication attempt
        c = cr.create_communication_from_request(status="in-progress")
        comm = Communication(c)
        try:
            if not patient.generalPractitioner:
                practitioner=None
            else:

                practitioner = resolve_reference(patient.generalPractitioner[0].reference)
            expanded_payload = expand_template_args(
                content=cr.payload[0].contentString,
                patient=patient,
                practitioner=practitioner)
            resulting_communication = HAPI_request('POST', 'Communication', resource=comm.as_json())
            audit_entry(
                f"Created Communication resource for the outgoing text",
                extra={"resource": resulting_communication},
                level='debug'
            )
            result = self.send_twilio_sms(message=expanded_payload, to_phone=target_phone)

        except TwilioRestException as ex:
            if ex.code == 21610:
                # In case of unsubcribed patient, mark as unsubscribed
                patient.unsubcribe()
                comm.status = "stopped"
            else:
                # For other causes of failed communication, mark the reason for failed request as unknown
                comm.status = "unknown"
                comm.statusReason = str(ex)

            audit_entry(
                "Twilio exception",
                extra={"resource": f"CommunicationResource/{cr.id}", "exception": ex},
                level='exception'
            )
            comm.persist()
            raise IsaccTwilioError(f"ERROR! {ex} raised attempting to send SMS")

        if result.status != 'sent' and result.status != 'queued':
            audit_entry(
                f"Twilio error",
                extra={"resource": result},
                level='error'
            )
            raise IsaccTwilioError(f"ERROR! Message status is neither sent nor queued. It was {result.status}")
        else:
            updated_cr = cr.mark_dispatched(expanded_payload, result)
            audit_entry(
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
        audit_entry(
            f"Twilio message created via API",
            extra={"twilio_message": message},
            level='debug'
        )
        return message

    def generate_incoming_message(self, message, time: datetime = None, patient: Patient=None, priority=None, themes=None,
                                  twilio_sid=None):
        if priority and priority not in ("routine", "urgent", "stat"):
            return f"Invalid priority given: {priority}. Only routine, urgent, and stat are allowed."

        if priority is None:
            priority = "routine"

        if patient is None:
            raise ValueError("Missing active patient")

        care_plan = patient.get_careplan()

        if not care_plan:
            error = "No CarePlan for this patient:"
            audit_entry(
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
        audit_entry(
            f"Created Communication resource for incoming text",
            extra={"resource": result},
            level='debug'
        )
        # look for participating practitioners in patient's care team
        # which always includes the generalPractitioners
        notify_emails = patient.get_care_team_emails()
        if len(notify_emails) > 0:
            send_message_received_notification(notify_emails, patient)
            patient.mark_followup_extension()

    def on_twilio_message_status_update(self, values):
        message_sid = values.get('MessageSid', None)
        message_status = values.get('MessageStatus', None)

        cr = HAPI_request('GET', 'CommunicationRequest', params={
            "identifier": f"http://isacc.app/twilio-message-sid|{message_sid}"
        })
        cr = first_in_bundle(cr)
        if cr is None:
            error = "No CommunicationRequest for this Twilio SID"
            audit_entry(
                error,
                extra={"message_sid": message_sid},
                level='error'
            )
            raise IsaccTwilioError(f"ERROR! {error}: {message_sid}")

        cr = CommunicationRequest(cr)
        patient = resolve_reference(cr.recipient[0].reference)

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
                # Callback only occurs on completed Communications
                c = cr.create_communication_from_request(status="completed")
                c = Communication(c)
                result = HAPI_request('POST', 'Communication', resource=c.as_json())
                audit_entry(
                    f"Created Communication resource on Twilio callback:",
                    extra={"resource": result},
                    level='debug'
                )
                # if this was a manual message, mark patient as having been followed up with
                if c.is_manual_follow_up_message():
                    patient.mark_followup_extension()
            else:
                # Update the status of the communication to completed
                comm = Communication(existing_comm)
                comm.status = "completed"
                result = comm.persist()
                audit_entry(
                    f"Received /MessageStatus callback with status {message_status} on existing Communication resource",
                    extra={"resource": result,
                           "new status": result.get('status'),
                           "message status": message_status},
                    level='debug'
                )

            cr.status = "completed"
            updated_cr = cr.persist()

            audit_entry(
                f"Updated CommunicationRequest and Communication due to twilio status update:",
                extra={"resource": f"CR: {updated_cr} \n Comm: {existing_comm}"},
                level='debug'
            )

            # maintain next outgoing and last followed up Twilio message
            # extensions after each send (now know to be complete)
            patient.mark_next_outgoing()
            patient.mark_followup_extension()

    def on_twilio_message_received(self, values):
        pt = HAPI_request('GET', 'Patient', params={
            "telecom": values.get("From", "+1").replace("+1", ""),
            "active": "true",
        })
        pt = first_in_bundle(pt)
        if not pt:
            error = "No active patient with this phone number"
            phone = values.get('From')
            audit_entry(
                error,
                extra={"from_phone": phone},
                level='error'
            )
            return f"{error}: {phone}"
        pt = Patient(pt)

        message = values.get("Body")
        # if the user requested to resubscribe, mark patient as active
        if "start" == message.lower().strip():
            pt.subscribe()
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
            audit_entry(
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
        skipped_crs = []

        now = datetime.now().astimezone()
        cutoff = now - timedelta(days=2)

        result = HAPI_request('GET', 'CommunicationRequest', params={
            "category": "isacc-scheduled-message,isacc-manually-sent-message",
            "status": "active",
            "occurrence": f"le{now.isoformat()}",
        })

        for cr_json in next_in_bundle(result):
            cr = CommunicationRequest(cr_json)
            patient = resolve_reference(cr.recipient[0].reference)

            # Happens when the patient removes their phone number completely.
            # Should not occur in production.
            try:
                patient_unsubscribed = any(
                    telecom_entry.system.lower() == 'sms' and telecom_entry.period.end
                    for telecom_entry in patient.telecom
                )
            except Exception as e:
                skipped_crs.append(cr)
                c = cr.create_communication_from_request(status="unknown")
                c = Communication(c)
                c.statusReason = str(e)
                result = HAPI_request('POST', 'Communication', resource=c.as_json())
                audit_entry(
                    f"Failed to send the message, {patient} does not have valid telecom",
                    extra={"resource": f"{result}", "exception": e},
                    level='exception'
                )
                # Display Twilio Error in a human readable form
                errors.append({'id': cr.id, 'error': str(e)})
                continue

            if cr.occurrenceDateTime.date < cutoff:
                # Anything older than cutoff will never be sent (#1861758)
                # and needs a status adjustment lest it throws off other queries
                # like next outgoing message time
                skipped_crs.append(cr)
                continue
            if patient_unsubscribed or not patient.active:
                if patient_unsubscribed:
                    c = cr.create_communication_from_request(status="stopped")
                    c = Communication(c)
                    result = HAPI_request('POST', 'Communication', resource=c.as_json())
                    audit_entry(
                        f"Generated Communication for unsubscribed patient",
                        extra={"resource": f"{result}"},
                        level='debug'
                    )
                skipped_crs.append(cr)
                continue
            try:
                self.process_cr(cr, successes)
            except Exception as e:
                audit_entry(
                    "Failed to send the message",
                    extra={"resource": f"CommunicationResource/{cr.id}", "exception": e},
                    level='exception'
                )
                skipped_crs.append(cr)
                errors.append({'id': cr.id, 'error': str(e)})

        for cr in skipped_crs:
            cr.status = "revoked"
            HAPI_request(
                "PUT",
                "CommunicationRequest",
                resource_id=cr.id,
                resource=cr.as_json())
            audit_entry(
                f"Skipped CommunicationRequest({cr.id}); status set to {cr.status}",
                extra={"CommunicationRequest": cr.as_json()})
            # as that message was likely the next-outgoing for the patient,
            # update the extension used to track next-outgoing-message time
            patient = resolve_reference(cr.recipient[0].reference)
            patient.mark_next_outgoing()

        return successes, errors

    def process_cr(self, cr: CommunicationRequest, successes: list):
        status = self.dispatch_cr(cr=cr)
        successes.append({'id': cr.id, 'status': status})
