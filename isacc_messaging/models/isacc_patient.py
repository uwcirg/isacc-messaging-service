"""ISACC Patient Module

Captures specialized methods needed by ISACC for Patients, not to be confused with the `fhirclient.Patient` class.
"""
from datetime import datetime, timedelta

from fhirclient.models.extension import Extension
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.patient import Patient


class IsaccPatient(Patient):

    def __init__(self, jsondict=None, strict=True):
        super(IsaccPatient, self).__init__(jsondict=jsondict, strict=strict)

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
        j = 0
        for j, extension in zip(range(0, len(self.extension)), self.extension):
            if extension.url == url:
                # properties won't allow assignment.  pop the old extension and replace
                del self.extension[j]
                break
        self.extension.append(Extension({"url": url, attribute: value}))

    def mark_next_outgoing(self):
        """Patient's get a special identifier for time of next outgoing message

        This method calculates and updates the identifier
        """
        next_outgoing_time = self._lookup_next_outgoing()

        # without any pending outgoing messages, add a bogus value
        # 50 years ago, to keep the patient in the search
        if not next_outgoing_time:
            next_outgoing_time = FHIRDate((datetime.now().astimezone() - timedelta(days=50*365.25)).isoformat())

        url = "http://isacc.app/date-time-of-next-outgoing-message"
        self.set_extension(url=url, value=next_outgoing_time, attribute="valueDateTime")

