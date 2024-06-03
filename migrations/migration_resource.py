"""Migration Resource

Defines a FHIR resource holding data about the latest migration by specializing
the `fhirclient.Basic` class. A single Basic resource is maintained with the most
recently (successfully) run migration revision held in the single Basic.code value.
"""
import os
import requests
import json
import logging
from fhirclient.models.basic import Basic

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

fhir_url = os.getenv("FHIR_URL", 'http://fhir-internal:8080/fhir/')
MIGRATION_SYSTEM = "http://fhir.migration.system"
MIGRATION_RESOURCE_ID = os.getenv("MIGRATION_RESOURCE_ID", "e61c4580-2493-417f-a26c-26faa8eb70ba")


class MigrationManager(Basic):
    """Represents a FHIR resource for managing migrations."""
    search_params = {"identifier": f'{MIGRATION_SYSTEM}|{MIGRATION_RESOURCE_ID}'}

    def __init__(self, jsondict=None, strict=True):
        super(Basic, self).__init__(jsondict=jsondict, strict=strict)
        # The extension class init does not define these fields as None
        self.author = None
        self.subject = None
        self.created = None

    def __repr__(self):
        return f"{self.resource_type}/{self.id}"

    @staticmethod
    def get_manager(create_if_not_found=True) -> 'MigrationManager':
        """Search for the Migration Manager. If specified, create one when not found"""
        basic = MigrationManager.get_resource()
        if basic is None and create_if_not_found:
            logger.debug("Creating new resource")
            basic = MigrationManager.persist()
            return MigrationManager(basic)
        elif basic is None and not create_if_not_found:
            return None

        return MigrationManager(basic)

    @staticmethod
    def get_resource():
        # GET request to retrieve the resource
        headers = {
            'Content-Type': 'application/fhir+json',
            'Cache-Control': 'no-cache'
        }

        response = requests.get(
            f"{fhir_url}Basic",
            params=MigrationManager.search_params,
            headers=headers
        )
        response.raise_for_status()

        basic = first_in_bundle(response.json())

        return basic

    @staticmethod
    def persist(resource = None):
        """Persist Basic state to FHIR store"""
        if not resource:
            resource = {
                "resourceType": "Basic",
                "identifier": [
                    {
                        "system": MIGRATION_SYSTEM,
                        "value": MIGRATION_RESOURCE_ID
                    }
                ],
                "code": {
                    "coding": [
                        {
                            "system": "http://our.migration.system",
                            "code": "updated-code"
                        }
                    ]
                },
            }
        resource_json = json.dumps(resource)
        headers = {
            'Content-Type': 'application/fhir+json'
        }

        response = requests.put(
            f"{fhir_url}Basic",
            params=MigrationManager.search_params,
            headers=headers,
            data=resource_json
        )
        response.raise_for_status()

        return response.json()

    def update_migration(self, migration_id: str):
        """Update the migration id on the FHIR"""
        self.code.coding[0].code = migration_id

        response = MigrationManager.persist(self.as_json())
        return response

    def get_latest_migration(self):
        """Returns the most recent ran migration"""
        current_migration = self.code.coding[0].code
        return current_migration


def first_in_bundle(bundle):
    """Return first resource in bundle

    :param bundle:  Fresh JSON bundle from FHIR store
    :return: first resource found in bundle
    """
    if bundle['resourceType'] == 'Bundle':
        if bundle['total'] > 0:
            return bundle['entry'][0]['resource']
