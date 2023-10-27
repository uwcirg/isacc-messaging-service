"""ISACC Practitioner Module

Captures common methods needed by ISACC for Practitioners, by specializing the `fhirclient.Practitioner` class.
"""
from fhirclient.models.careteam import CareTeam
from fhirclient.models.practitioner import Practitioner

from isacc_messaging.models.fhir import (
    HAPI_request,
    IsaccFhirException,
    next_in_bundle,
    resolve_reference,
)


class IsaccPractitioner(Practitioner):

    def __init__(self, jsondict=None, strict=True):
        super(IsaccPractitioner, self).__init__(jsondict=jsondict, strict=strict)

    @staticmethod
    def active_practitioners():
        """Execute query for active practitioners

        :returns: bundle of practitioners, in JSON format
        """
        # TODO consider active flag when set on all practitioners
        response = HAPI_request('GET', 'Practitioner')
        return response

    @property
    def email_address(self):
        """Shortcut to obtain primary email from nested telecom list"""
        for t in self.telecom:
            if t.system == "email":
                return t.value

    def get_phone_number(self) -> str:
        if self.telecom:
            for t in self.telecom:
                if t.system == 'sms':
                    return t.value
        raise IsaccFhirException(f"Error: {self} doesn't have an sms contact point on file")

    def practitioner_patients(self):
        """Return bundle of patients for which this practitioner is a primary or secondary

        :returns: list of Patient objects
        """
        careteams = HAPI_request("GET", "CareTeam", params={"participant": f"Practitioner/{self.id}"})
        patients = []
        for ct in next_in_bundle(careteams):
            # Each care team has one patient at subject/reference
            careteam = CareTeam(ct)
            patients.append(resolve_reference(careteam.subject.reference))
        return patients

    def persist(self):
        """Persist self state to FHIR store"""
        response = HAPI_request(
            method="PUT",
            resource_type=self.resource_type,
            resource_id=self.id,
            resource=self.as_json())
        return response
