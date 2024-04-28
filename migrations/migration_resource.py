"""Migration Resource

Defines a FHIR resource holding data about latest migration by specializing
the `fhirclient.Basic` class.
A single Basic resource is maintained with the most 
recently (successfully) run migration revision held in the single Basic.code value.
"""
from isacc_messaging.models.isacc_fhirdate import (
    IsaccFHIRDate as FHIRDate,
)

from datetime import datetime

from fhirclient.models.basic import Basic
from isacc_messaging.models.fhir import (
    HAPI_request,
)

class MigrationManager(Basic):
    def __init__(self, jsondict=None, strict=True):
        super(Basic, self).__init__(jsondict=jsondict, strict=strict)

    def __repr__(self):
        return f"{self.resource_type}/{self.id}"

    @staticmethod
    def create_resource(resource = None):
        """Create a new Migration Manager"""
        response = HAPI_request('POST', 'Basic', resource=resource)
        return response

    @staticmethod
    def get_resource(params=None):
        """Search for the Migration Manager"""
        response = HAPI_request('GET', 'Basic', params=params)
        return response

    def persist(self):
        """Persist self state to FHIR store"""
        response = HAPI_request(
            method="PUT",
            resource_type=self.resource_type,
            resource_id=self.id,
            resource=self.as_json())
        return response

    def update_migration(self, migration_id: str):
        """Update the migration code on the FHIR"""
        self.created = FHIRDate(datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'))
        self.code.coding[0].code = migration_id

        # The extension class init does not define these fields as None
        self.author = None
        self.subject = None
        self.identifier = None

        response = self.persist()
        return response

    def get_latest_migration(self):
        """Returns most recent available migration"""
        current_migration = self.code.coding[0].code
        return current_migration
