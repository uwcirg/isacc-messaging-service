"""Migration Resource

Defines a FHIR resource holding data about the latest migration by specializing
the `fhirclient.Basic` class. A single Basic resource is maintained with the most 
recently (successfully) run migration revision held in the single Basic.code value.
"""
from datetime import datetime
import os
from fhirclient.models.basic import Basic
from isacc_messaging.models.isacc_fhirdate import IsaccFHIRDate as FHIRDate
from isacc_messaging.models.fhir import first_in_bundle
import requests
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

fhir_url = 'http://fhir-internal:8080/fhir/'
MIGRATION_SYSTEM = "http://fhir.migration.system"
MIGRATION_RESOURCE_ID = os.getenv("MIGRATION_RESOURCE_ID", "1236")


class MigrationManager(Basic):
    """Represents a FHIR resource for managing migrations."""
    search_params = {"identifier": f'{MIGRATION_SYSTEM}|{MIGRATION_RESOURCE_ID}'}

    def __init__(self, jsondict=None, strict=True):
        super(Basic, self).__init__(jsondict=jsondict, strict=strict)

    def __repr__(self):
        return f"{self.resource_type}/{self.id}"

    @staticmethod
    def create_resource(resource=None) -> 'MigrationManager':
        """Create a new Migration Manager storing the latest applied migration id"""

        if resource is None:
            # Define the resource data
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
                "created": datetime.now().astimezone().isoformat()
            }

        response = MigrationManager.persist(resource)
        print("HAPI PUT call response", response)
        new_manager = MigrationManager(response)

        return new_manager


    @staticmethod
    def get_resource(create_if_not_found=True) -> 'MigrationManager':
        """Search for the Migration Manager. If specified, create one when not found"""
        response = requests.get(
            f'{fhir_url}Basic', params=MigrationManager.search_params)
        response.raise_for_status()
        basic = first_in_bundle(response.json())
        logger.debug("result of GET, ", response.json())
        if basic is None and create_if_not_found:
            logger.debug("Creating new resource")
            return MigrationManager.persist()
        elif basic is None and not create_if_not_found:
            return None

        return MigrationManager(basic)


    @staticmethod
    def create_new_resource():
        # Define the FHIR server URL and the identifier

        # Define the resource data
        resource = {
            "resourceType": "Basic",
            "identifier": [
                {
                    "system": MIGRATION_SYSTEM,
                    "value": resource_id
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
            "created": datetime.now().astimezone().isoformat()
        }

        # Convert the resource to a JSON string
        resource_json = json.dumps(resource)

        # Headers
        headers = {
            'Content-Type': 'application/fhir+json'
        }

        # PUT request to create or update the resource
        put_response = requests.put(
            f"{fhir_url}Basic",
            params=search_params,
            headers=headers,
            data=resource_json
        )
        put_response.raise_for_status()

        print("PUT Response Status Code:", put_response.status_code)
        print("PUT Response Body:", put_response.json())

    @staticmethod
    def get_new_resource():
        # GET request to retrieve the resource
        headers = {
            'Content-Type': 'application/fhir+json'
        }

        get_response = requests.get(
            f"{fhir_url}Basic",
            params=MigrationManager.search_params,
            headers=headers
        )
        get_response.raise_for_status()

        print("GET Response Status Code:", get_response.status_code)
        print("GET Response Body:", get_response.json())


    @staticmethod
    def get_resource_hapi() -> 'MigrationManager':
        """Search for the Migration Manager. If specified, create one when not found"""
        response = requests.get(f"{fhir_url}Basic", params=MigrationManager.search_params)
        response.raise_for_status()
        basic = first_in_bundle(response.json())

        if basic is None:
            print("HAPI_request did not find the Basic ", response.json())
        else:
            print("HAPI_request Found Basic, reponse is ", response.json())


    @staticmethod
    def create_resource_hapi(resource = None):
        """Persist Basic state to FHIR store"""
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
            "created": datetime.now().astimezone().isoformat()
        }

        response = requests.put(
            f"{fhir_url}Basic", json=resource, params=MigrationManager.search_params)
        response.raise_for_status()
        print("Result of HAPI_request PUT ", response.json())
        return response.json()


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
                "created": datetime.now().astimezone().isoformat()
            }

        logger.debug("attempt to PUT new Basic resource...")
        response = requests.put(
            f"{fhir_url}Basic",
            json=resource,
            params=MigrationManager.search_params,
        )
        response.raise_for_status()
        logger.debug("Result of HAPI_request PUT ", response.json())
        return response


    def update_migration(self, migration_id: str):
        """Update the migration id on the FHIR"""
        self.created = FHIRDate(datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'))
        self.code.coding[0].code = migration_id

        # The extension class init does not define these fields as None
        self.author = None
        self.subject = None
        self.identifier = None

        response = MigrationManager.persist(self.as_json())
        return response

    def get_latest_migration(self):
        """Returns the most recent ran migration"""
        current_migration = self.code.coding[0].code
        return current_migration
