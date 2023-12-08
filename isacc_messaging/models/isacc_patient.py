"""ISACC Patient Module

Captures common methods needed by ISACC for Patients, by specializing the `fhirclient.Patient` class.
"""
from fhirclient.models.extension import Extension
from fhirclient.models.patient import Patient
import logging

from isacc_messaging.audit import audit_entry
from isacc_messaging.models.isacc_communication import IsaccCommunication as Communication
from isacc_messaging.models.isacc_fhirdate import (
    DEEP_FUTURE,
    DEEP_PAST,
    IsaccFHIRDate as FHIRDate,
)
from isacc_messaging.models.fhir import HAPI_request, IsaccFhirException, next_in_bundle

# URLs for patient extensions
LAST_UNFOLLOWEDUP_URL = "http://isacc.app/time-of-last-unfollowedup-message"
NEXT_OUTGOING_URL = "http://isacc.app/date-time-of-next-outgoing-message"


class IsaccPatient(Patient):

    def __init__(self, jsondict=None, strict=True):
        super(IsaccPatient, self).__init__(jsondict=jsondict, strict=strict)

    def __repr__(self):
        return f"{self.resource_type}/{self.id}"

    @staticmethod
    def active_patients():
        """Execute query for active patients

        NB, returns only patients with active set to true
        """
        response = HAPI_request('GET', 'Patient', params={
            "active": True
        })
        return response

    @staticmethod
    def get_patient_by_id(id):
        """Execute query for active patients

        NB, returns only patients with active set to true
        """
        response = HAPI_request('GET', 'Patient', params={
            "id": id
        })
        return response
    
    @staticmethod
    def all_patients():
        """Execute query for all patients

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
        from fhirclient.models.fhirdate import FHIRDate as BaseFHIRDate
        retval = None
        if not self.extension:
            return

        for extension in self.extension:
            if extension.url == url:
                retval = getattr(extension, attribute)

        # FHIRDates are challenging to work with.  Convert to specialized isacc_fhirdate if
        # types match
        if isinstance(retval, BaseFHIRDate):
            retval = FHIRDate(retval.isostring)
        return retval

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

    def mark_next_outgoing(self, persist_on_change=True):
        """Patient's get a special extension for time of next outgoing message

        All Patients maintain a single extension with url "http://isacc.app/date-time-of-next-outgoing-message"
        to track the time of the next message scheduled to be sent to the patient, cleared only once no
        scheduled messages exist for the patient.

        An extension is used to track as it is necessary when used as the sort-by column on patients.

        :param persist_on_change: set false to skip persisting any patient changes to db

        This idempotent method calculates and updates the appropriate extension
        """
        from isacc_messaging.models.isacc_communicationrequest import IsaccCommunicationRequest as CommunicationRequest
        next_outgoing = CommunicationRequest.next_by_patient(self)

        # without any pending outgoing messages, add a bogus value deep in the past to keep the patient in
        # the search (searching by extension will eliminate patients without said extension)
        if not next_outgoing:
            save_value = DEEP_PAST
        else:
            save_value = FHIRDate(next_outgoing.occurrenceDateTime.isostring)

        existing = self.get_extension(url=NEXT_OUTGOING_URL, attribute="valueDateTime")
        if save_value != existing:
            logging.debug(f"set Patient({self.id}) extension {NEXT_OUTGOING_URL}: {save_value} (was {existing})")
            self.set_extension(url=NEXT_OUTGOING_URL, value=save_value.isostring, attribute="valueDateTime")
            if persist_on_change:
                result = self.persist()
                audit_entry(
                    f"Updated Patient({self.id}) next-outgoing extension to {save_value}",
                    extra={"resource": result},
                    level='debug'
                )

    def mark_followup_extension(self, persist_on_change=True):
        """Maintain extension value on the patient at all times to track time since message received

        All Patients maintain a single extension with url "http://isacc.app/time-of-last-unfollowedup-message"
        to track the time since the earliest message was received from the patient, cleared only once
        a message is manually sent to the user, indicating a direct response.

        An extension is used to track as it is necessary when used as the sort-by column on patients.

        The value of the extension is:
        - 50 years in the future (for clean sort order), if user has not sent a message since the most recent followup
        - the oldest value_date_time of any messages from the user since the last manually-sent message to the user

        :param persist_on_change: set false to skip persisting patient change to db

        This idempotent method calculates and updates the appropriate extension
        """
        most_recent_followup = None
        for c in next_in_bundle(Communication.for_patient(self, category="isacc-manually-sent-message")):
            most_recent_followup = FHIRDate(c["sent"])
            break
        # also possible a followup was recorded as `outside communication`
        for c in next_in_bundle(Communication.about_patient(self)):
            # only consider outside communications reported to have been `sent`
            if "sent" in c:
                if most_recent_followup is None:
                    most_recent_followup = FHIRDate(c["sent"])
                most_recent_followup = max(most_recent_followup, FHIRDate(c["sent"]))
                break

        oldest_reply = None
        for c in next_in_bundle(Communication.from_patient(self)):
            potential = FHIRDate(c["sent"])
            # if the message predates the latest followup, we're done looking
            if most_recent_followup and most_recent_followup > potential:
                break
            oldest_reply = potential

        save_value = oldest_reply
        if not oldest_reply:
            # without any pending outgoing messages, add a bogus value deep in the past to keep the patient
            # in the search (searching by extension will eliminate patients without said extension)
            save_value = DEEP_FUTURE

        existing = self.get_extension(url=LAST_UNFOLLOWEDUP_URL, attribute="valueDateTime")
        if save_value != existing:
            logging.debug(f"set Patient({self.id}) extension {LAST_UNFOLLOWEDUP_URL}: {save_value} (was {existing})")
            self.set_extension(url=LAST_UNFOLLOWEDUP_URL, value=save_value.isostring, attribute="valueDateTime")
            if persist_on_change:
                result = self.persist()
                audit_entry(
                    f"Updated Patient({self.id}) last-unfollowed-up extension to {save_value}",
                    extra={"resource": result},
                    level='debug'
                )

    def is_test_patient(self):
        """Shortcut to see if meta.security list includes HTEST value"""
        test_system = "http://terminology.hl7.org/CodeSystem/v3-ActReason"
        if not self.meta.security:
            return

        vals = [i.code for i in self.meta.security if i.system == test_system]
        if vals and "HTEST" in vals:
            return True

    def persist(self):
        """Persist self state to FHIR store"""
        response = HAPI_request(
            method="PUT",
            resource_type=self.resource_type,
            resource_id=self.id,
            resource=self.as_json())
        return response

    def deactivate(self):
        """Persist self state to FHIR store"""
        self.active = False
        response = HAPI_request(
            method="PUT",
            resource_type=self.resource_type,
            resource_id=self.id,
            resource=self.as_json())
        return response

