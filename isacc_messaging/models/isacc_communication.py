"""ISACC Communication Module

Captures common methods needed by ISACC for Communications, by specializing
the `fhirclient.Communication` class.
"""
from fhirclient.models.communication import Communication

from isacc_messaging.models.fhir import HAPI_request


class IsaccCommunication(Communication):

    def __init__(self, jsondict=None, strict=True):
        super(IsaccCommunication, self).__init__(jsondict=jsondict, strict=strict)

    def __repr__(self):
        return f"{self.resource_type}/{self.id}"

    def is_manual_follow_up_message(self) -> bool:
        """returns true IFF the communication category shows manually sent"""
        for category in self.category:
            for coding in category.coding:
                if coding.system == 'https://isacc.app/CodeSystem/communication-type':
                    if coding.code == 'isacc-manually-sent-message':
                        return True

    def persist(self):
        """Persist self state to FHIR store"""
        response = HAPI_request('PUT', 'Communication', resource_id=self.id, resource=self.as_json())
        return response

    def change_status(self, status):
        """Persist self state to FHIR store"""
        self.status = status
        response = self.persist()
        return response

    @staticmethod
    def about_patient(patient):
        """Query for "outside" Communications about the patient

        This includes the dummy Communications added when staff resolve
        a message without a response (category:isacc-message-resolved-no-send)

        NB: only `sent` or `received` will have a valueDateTime depending on
        direction of outside communication.  `sent` implies communication from
        practitioner, `received` implies communication from patient.
        """
        return HAPI_request("GET", "Communication", params={
            "category": "isacc-non-sms-message,isacc-message-resolved-no-send",
            "subject": f"Patient/{patient.id}",
            "_sort": "-sent",
        })

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
