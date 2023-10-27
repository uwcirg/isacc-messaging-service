"""ISACC Patient Module

Captures common methods needed by ISACC for Patients, by specializing the `fhirclient.Patient` class.
"""
from datetime import datetime, timedelta
from fhirclient.models.extension import Extension
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.patient import Patient
import logging

from isacc_messaging.audit import audit_entry
from isacc_messaging.models.isacc_communication import IsaccCommunication as Communication
from isacc_messaging.models.fhir import HAPI_request, IsaccFhirException, next_in_bundle

# URLs for patient extensions
LAST_UNFOLLOWEDUP_URL = "http://isacc.app/time-of-last-unfollowedup-message"
NEXT_OUTGOING_URL = "http://isacc.app/date-time-of-next-outgoing-message"


class IsaccPatient(Patient):

    def __init__(self, jsondict=None, strict=True):
        super(IsaccPatient, self).__init__(jsondict=jsondict, strict=strict)

    @staticmethod
    def active_patients():
        """Execute query for active patients

        NB, until status is set on all patients, queries for
        any status/active value will skip those without a value.
        """
        response = HAPI_request('GET', 'Patient')
        return response

    def get_phone_number(self) -> str:
        if self.telecom:
            for t in self.telecom:
                if t.system == 'sms':
                    return t.value
        raise IsaccFhirException(f"Error: {self} doesn't have an sms contact point on file")

    def get_extension(self, url, attribute):
        """Get current value for extension of given url, or None if not found

        :param url: like a system on a code, used to identify meaning of the extension
        :param attribute: as FHIR names different attributes depending on data type, name
          attribute to use, i.e. "valueDateTime" or "valueInt"

        FHIR includes an [extensibility](http://hl7.org/fhir/R4/extensibility.html) framework
        for most resources.  This method will return the current value to an extension on the
        Patient resource, with the matching url, or None if not found.
        """
        if not self.extension:
            return

        for extension in self.extension:
            if extension.url == url:
                return getattr(extension, attribute)

    def set_extension(self, url, value, attribute):
        """Set value for extension on patient to given value.

        :param url: like a system on a code, used to identify meaning of the extension
        :param value: value, of datatype expected for named attribute, to set
        :param attribute: as FHIR names different attributes depending on data type, name
          attribute to use, i.e. "valueDateTime" or "valueInt"

        FHIR includes an [extensibility](http://hl7.org/fhir/R4/extensibility.html) framework
        for most resources.  This method will add an extension to the Patient
        or set the value, such that only a single extension of the given
        url exists at any time.
        """
        if self.extension is None:
            self.extension = []

        keepers = []
        for extension in self.extension:
            # properties won't allow assignment.  delete the old and replace
            if extension.url != url:
                keepers.append(extension)
        if len(keepers) != len(self.extension):
            self.extension = keepers

        self.extension.append(Extension({"url": url, attribute: value}))

    def mark_next_outgoing(self, verbosity=0):
        """Patient's get a special extension for time of next outgoing message

        All Patients maintain a single extension with url "http://isacc.app/date-time-of-next-outgoing-message"
        to track the time of the next message scheduled to be sent to the patient, cleared only once no
        scheduled messages exist for the patient.

        An extension is used to track as it is necessary when used as the sort-by column on patients.

        :param verbosity: set to positive number to increase reporting noise

        This idempotent method calculates and updates the appropriate extension
        """
        from isacc_messaging.models.isacc_communicationrequest import IsaccCommunicationRequest as CommunicationRequest
        next_outgoing = CommunicationRequest.next_by_patient(self)

        # without any pending outgoing messages, add a bogus value
        # 50 years ago, to keep the patient in the search
        if not next_outgoing:
            next_outgoing_time = FHIRDate((datetime.now().astimezone() - timedelta(days=50*365.25)).isoformat())
        else:
            next_outgoing_time = next_outgoing.occurrenceDateTime

        if verbosity > 0:
            logging.info(f"Patient {self.id} next outgoing: {next_outgoing_time.isostring}")

        current_value = self.get_extension(url=NEXT_OUTGOING_URL, attribute="valueDateTime")
        cv = current_value.isostring if current_value else None
        if verbosity > 1:
            logging.info(f"current next_outgoing value {cv}")
        if cv and cv != next_outgoing_time.isostring:
            logging.debug(f"updating user {self.id} next outgoing to {next_outgoing_time.isostring}")
            self.set_extension(url=NEXT_OUTGOING_URL, value=next_outgoing_time.isostring, attribute="valueDateTime")

    def mark_followup_extension(self, verbosity=0):
        """Maintain extension value on the patient at all times to track time since message received

        All Patients maintain a single extension with url "http://isacc.app/time-of-last-unfollowedup-message"
        to track the time since the earliest message was received from the patient, cleared only once
        a message is manually sent to the user, indicating a direct response.

        An extension is used to track as it is necessary when used as the sort-by column on patients.

        The value of the extension is:
        - 50 years in the future (for clean sort order), if user has not sent a message since the most recent followup
        - the oldest value_date_time of any messages from the user since the last manually-sent message to the user

        :param verbosity: set to positive number to increase reporting noise

        This idempotent method calculates and updates the appropriate extension
        """
        most_recent_followup = None
        for c in next_in_bundle(Communication.for_patient(self, category="isacc-manually-sent-message")):
            most_recent_followup = FHIRDate(c.sent)
            break

        oldest_reply = None
        for c in next_in_bundle(Communication.from_patient(self)):
            potential = FHIRDate(c.sent)
            # if the message predates the latest followup, we're done looking
            if most_recent_followup and most_recent_followup.date > potential:
                break
            oldest_reply = potential

        save_value = oldest_reply
        if not oldest_reply:
            # Set to 50 years in the future for patient sort by functionality
            save_value = FHIRDate((datetime.now().astimezone() + timedelta(days=50*365.25)).isoformat())

        existing = self.get_extension(url=LAST_UNFOLLOWEDUP_URL, attribute="valueDateTime")
        if existing.date != save_value.date:
            self.set_extension(url=LAST_UNFOLLOWEDUP_URL, value=save_value.isostring, attribute="valueDateTime")
            result = HAPI_request('PUT', 'Patient', resource_id=patient.id, resource=patient.as_json())
            audit_entry(
                f"Updated Patient resource, last-unfollowedup extension",
                extra={"resource": result},
                level='debug'
            )
        elif verbosity > 0:
            logging.info(f"current value for {self}:{LAST_UNFOLLOWEDUP_URL} found to be accurate")

    def persist(self):
        """Persist self state to FHIR store"""
        response = HAPI_request(
            method="PUT",
            resource_type=self.resource_type,
            resource_id=self.id,
            resource=self.as_json())
        return response
