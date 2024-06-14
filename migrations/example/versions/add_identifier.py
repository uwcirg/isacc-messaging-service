import requests
import json
import logging
import os

# Migration script generated for add_identifier
revision = 'd5a1c49e-8efb-4610-b9d3-f59f98541f16'
down_revision = '985f4e1e-29f5-4911-bc9c-2c774b685289'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the FHIR server base URL
FHIR_SERVER_URL = os.getenv('FHIR_URL')
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
        "identifier": [
            {
                "system": "uwDAL_Clarity",
                "value": "12345"
            }
        ],
        "gender": "male",
        "birthDate": "1980-01-01",
        "telecom": [
            {
                "system": "phone",
                "value": "555-555-5555",
                "use": "home"
            }
        ]
    }
    response = requests.put(f'{FHIR_SERVER_URL}/Patient/{PATIENT_ID}', headers=HEADERS, data=json.dumps(patient_resource))
    if response.status_code == 200 or response.status_code == 201:
        logging.info('Patient updated successfully with phone number.')
    else:
        logging.error(f'Failed to update patient: {response.status_code} {response.text}')

def downgrade():
    # Defines downgrading function ran on downgrade command
    response = requests.get(f'{FHIR_SERVER_URL}/Patient/{PATIENT_ID}', headers=HEADERS)
    if response.status_code == 200:
        patient_resource = response.json()
        # Remove the phone number if it exists
        if 'telecom' in patient_resource:
            patient_resource['telecom'] = [entry for entry in patient_resource['telecom'] if entry['system'] != 'phone' or entry['value'] != '555-555-5555']
        response = requests.put(f'{FHIR_SERVER_URL}/Patient/{PATIENT_ID}', headers=HEADERS, data=json.dumps(patient_resource))
        if response.status_code == 200 or response.status_code == 201:
            logging.info('Patient phone number removed successfully.')
        else:
            logging.error(f'Failed to update patient: {response.status_code} {response.text}')
    else:
        logging.error(f'Failed to fetch patient: {response.status_code} {response.text}')