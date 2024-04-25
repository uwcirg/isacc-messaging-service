"""Migration Module

Captures common methods needed by the system for migrations, by specializing
the `fhirclient.Basic` class.
"""
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
        response = HAPI_request('PUT', 'Communication', resource_id=self.id, resource=self.as_json())
        return response

    def update_migration(self, migration_id):
        """Persist self state to FHIR store"""
        self.code = {"coding": [{ "system": "http://our.migration.system", "code": migration_id}]}
        response = self.persist()
        return response
    
    def get_migration(self):
        """Returns most recent available migration"""
        current_migration = self.code["coding"][0]["code"]
        return current_migration
