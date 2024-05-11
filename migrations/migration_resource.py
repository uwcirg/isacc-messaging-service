"""Migration Resource

Defines a FHIR resource holding data about the latest migration by specializing
the `fhirclient.Basic` class. A single Basic resource is maintained with the most 
recently (successfully) run migration revision held in the single Basic.code value.
"""
from datetime import datetime

from fhirclient.models.basic import Basic
from isacc_messaging.models.isacc_fhirdate import IsaccFHIRDate as FHIRDate
from isacc_messaging.models.fhir import first_in_bundle, HAPI_request

class MigrationManager(Basic):
    """Represents a FHIR resource for managing migrations."""
    def __init__(self, jsondict=None, strict=True):
        super(Basic, self).__init__(jsondict=jsondict, strict=strict)

    def __repr__(self):
        return f"{self.resource_type}/{self.id}"

    @staticmethod
    def create_resource(resource=None) -> 'MigrationManager':
        """Create a new Migration Manager storing the latest applied migration id"""
        created_time = datetime.now().astimezone().isoformat()

        if resource is None:
            resource = {
                'resourceType': 'Basic',
                'code': {"coding": [{"system": "http://our.migration.system", "code": None}]},
                'created': created_time,
            }

        response = HAPI_request('POST', 'Basic', resource=resource)
        new_manager = MigrationManager(response)

        return new_manager

    @staticmethod
    def get_resource(create_if_not_found=True, params=None) -> 'MigrationManager':
        """Search for the Migration Manager. If specified, create one when not found"""
        response = HAPI_request('GET', 'Basic', params=params)
        basic = first_in_bundle(response)

        if basic is None and create_if_not_found:
            return MigrationManager.create_resource()
        elif basic is None and not create_if_not_found:
            return None

        manager = MigrationManager(basic)

        return manager

    def persist(self):
        """Persist self state to FHIR store"""
        response = HAPI_request(
            method="PUT",
            resource_type=self.resource_type,
            resource_id=self.id,
            resource=self.as_json())
        return response

    def update_migration(self, migration_id: str):
        """Update the migration id on the FHIR"""
        self.created = FHIRDate(datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'))
        self.code.coding[0].code = migration_id

        # The extension class init does not define these fields as None
        self.author = None
        self.subject = None
        self.identifier = None

        response = self.persist()
        return response

    def get_latest_migration(self):
        """Returns the most recent ran migration"""
        current_migration = self.code.coding[0].code
        return current_migration
