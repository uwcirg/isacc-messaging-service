"""ISACC CommunicationRequest Module

Captures common methods needed by ISACC for CommunicationRequests, by specializing
the `fhirclient.CommunicationRequest` class.
"""
from datetime import datetime
from fhirclient.models.communicationrequest import CommunicationRequest
from fhirclient.models.identifier import Identifier

from isacc_messaging.models.fhir import HAPI_request, first_in_bundle


class IsaccCommunicationRequest(CommunicationRequest):

    def __init__(self, jsondict=None, strict=True):
        super(IsaccCommunicationRequest, self).__init__(jsondict=jsondict, strict=strict)

    def __repr__(self):
        return f"{self.resource_type}/{self.id}"

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

    def dispatched(self):
        return self.identifier and len([i for i in self.identifier if i.system == "http://isacc.app/twilio-message-sid"]) > 0

    def dispatched_message_status(self):
            sid = ""
            status = ""
            as_of = ""
            for i in self.identifier:
                for e in i.extension:
                    if e.url == "http://isacc.app/twilio-message-status":
                        status = e.valueCode
                    if e.url == "http://isacc.app/twilio-message-status-updated":
                        as_of = e.valueDateTime.isostring
                if i.system == "http://isacc.app/twilio-message-sid":
                    sid = i.value
            return f"Twilio message (sid: {sid}, CR.id: {self.id}) was previously dispatched. Last known status: {status} (as of {as_of})"

    def mark_dispatched(self, expanded_payload, result):
            self.payload[0].contentString = expanded_payload
            if not self.identifier:
                self.identifier = []
            self.identifier.append(Identifier({
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
            updated_cr = HAPI_request('PUT', 'CommunicationRequest', resource_id=self.id, resource=self.as_json())
            return updated_cr

    def create_communication_from_request(self, status = "completed"):
        if self.category[0].coding[0].code == 'isacc-manually-sent-message':
            code = 'isacc-manually-sent-message'
        else:
            code = "isacc-auto-sent-message"
        return {
            "resourceType": "Communication",
            "id": str(self.id),
            "basedOn": [{"reference": f"CommunicationRequest/{self.id}"}],
            "partOf": [{"reference": f"{self.basedOn[0].reference}"}],
            "category": [{
                "coding": [{
                    "system": "https://isacc.app/CodeSystem/communication-type",
                    "code": code
                }]
            }],

            "payload": [p.as_json() for p in self.payload],
            "sent": datetime.now().astimezone().isoformat(),
            "sender": self.sender.as_json() if self.sender else None,
            "recipient": [r.as_json() for r in self.recipient],
            "medium": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/ValueSet/v3-ParticipationMode",
                    "code": "SMSWRIT"
                }]
            }],
            "note": [n.as_json() for n in self.note] if self.note else None,
            "status": status
        }

    def persist(self):
        """Persist self state to FHIR store"""
        response = HAPI_request('PUT', 'CommunicationRequest', resource_id=self.id, resource=self.as_json())
        return response
