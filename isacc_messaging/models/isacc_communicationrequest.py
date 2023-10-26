"""ISACC CommunicationRequest Module

Captures common methods needed by ISACC for CommunicationRequests, by specializing
the `fhirclient.CommunicationRequest` class.
"""
from fhirclient.models.communicationrequest import CommunicationRequest

from isacc_messaging.models.fhir import HAPI_request, first_in_bundle


class IsaccCommunicationRequest(CommunicationRequest):

    def __init__(self, jsondict=None, strict=True):
        super(IsaccCommunicationRequest, self).__init__(jsondict=jsondict, strict=strict)

    @staticmethod
    def next_by_patient(patient):
        """Lookup next active CommunicationRequest for given patient"""
        response = HAPI_request('GET', 'CommunicationRequest', params={
            "category": "isacc-scheduled-message,isacc-manually-sent-message",
            "status": "active",
            "recipient": f"Patient/{patient.id}",
            "_sort": "occurrence",
            "_maxresults": 1
        })
        first = first_in_bundle(response)
        if first:
            return CommunicationRequest(first)
