"""ISACC Patient Module

Captures common methods needed by ISACC for Patients, by specializing the `fhirclient.Patient` class.
"""
from datetime import datetime, timedelta
from fhirclient.models.extension import Extension
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.patient import Patient
import logging

from isacc_messaging.api.fhir import HAPI_request


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
                value = getattr(extension, attribute)()
                if attribute == "valueDateTime":
                    return FHIRDate(value)
                return value

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

        for j, extension in zip(range(0, len(self.extension)), self.extension):
            if extension.url == url:
                # properties won't allow assignment.  delete the old and replace
                del self.extension[j]
                break
        self.extension.append(Extension({"url": url, attribute: value}))

    def mark_next_outgoing(self, verbosity=0):
        """Patient's get a special identifier for time of next outgoing message

        :param verbosity: set to positive number to increase reporting noise

        This method calculates and updates the identifier
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

        url = "http://isacc.app/date-time-of-next-outgoing-message"
        if verbosity > 1:
            current_value = self.get_extension(url=url, attribute="valueDateTime")
            logging.info(f"current identifier value {current_value}")
        self.set_extension(url=url, value=next_outgoing_time.isostring, attribute="valueDateTime")

    def persist(self):
        """Persist self state to FHIR store"""
        response = HAPI_request(
            method="PUT",
            resource_type=self.resource_type,
            resource_id=self.id,
            resource=self.as_json())
        response.raise_for_status()
        return response.json()
