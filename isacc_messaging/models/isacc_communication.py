"""ISACC Communication Module

Captures common methods needed by ISACC for Communications, by specializing
the `fhirclient.Communication` class.
"""
from fhirclient.models.communication import Communication

from isacc_messaging.models.fhir import HAPI_request


class IsaccCommunication(Communication):

    def __init__(self, jsondict=None, strict=True):
        super(IsaccCommunication, self).__init__(jsondict=jsondict, strict=strict)

    def is_manual_follow_up_message(self) -> bool:
        """returns true IFF the communication category shows manually sent"""
        for category in self.category:
            for coding in category.coding:
                if coding.system == 'https://isacc.app/CodeSystem/communication-type':
                    if coding.code == 'isacc-manually-sent-message':
                        return True

    @staticmethod
    def for_patient(patient, category):
        """Query for all Communications intended for patient with matching code"""
        # TODO: limit by status?
        return HAPI_request('GET', 'Communication', params={
            "category": category,
            "recipient": f"Patient/{patient.id}",
            "_sort": "-sent",
        })

    @staticmethod
    def from_patient(patient):
        """Query for all Communications received from patient"""
        return HAPI_request('GET', 'Communication', params={
            "sender": f"Patient/{patient.id}",
            "_sort": "-sent",
        })
