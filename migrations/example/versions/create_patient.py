import requests
import json
import logging

# Migration script generated for add_active
revision = '985f4e1e-29f5-4911-bc9c-2c774b685289'
down_revision = 'None'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the FHIR server base URL
FHIR_SERVER_URL = 'http://localhost:8080/fhir'
PATIENT_ID = 'example'

# Headers for FHIR requests
HEADERS = {
    'Content-Type': 'application/fhir+json'
}

def upgrade():
    # Defines upgrading function ran on upgrade command
    patient_resource = {
        "resourceType": "Patient",
        "id": PATIENT_ID,
        "name": [
            {
                "use": "official",
                "family": "Doe",
                "given": [
                    "John",
                    "A"
                ]
            }
        ],
        "gender": "male",
        "birthDate": "1980-01-01"
    }
    response = requests.put(f'{FHIR_SERVER_URL}/Patient/{PATIENT_ID}', headers=HEADERS, data=json.dumps(patient_resource))
    if response.status_code == 200 or response.status_code == 201:
        logging.info('Patient created successfully.')
    else:
        logging.error(f'Failed to create patient: {response.status_code} {response.text}')

def downgrade():
    # Defines downgrading function ran on downgrade command
    response = requests.delete(f'{FHIR_SERVER_URL}/Patient/{PATIENT_ID}', headers=HEADERS)
    if response.status_code == 200 or response.status_code == 204:
        logging.info('Patient deleted successfully.')
    else:
        logging.error(f'Failed to delete patient: {response.status_code} {response.text}')
