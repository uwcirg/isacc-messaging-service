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
    response = requests.get(f'{FHIR_SERVER_URL}/Patient/{PATIENT_ID}', headers=HEADERS)
    if response.status_code == 200:
        patient_resource = response.json()
        if 'identifier' not in patient_resource:
            patient_resource['identifier'] = []
        patient_resource['identifier'].append({
            "use": "usual",
            "system": "http://hospital.smarthealthit.org",
            "value": "12345"
        })
        update_response = requests.put(f'{FHIR_SERVER_URL}/Patient/{PATIENT_ID}', headers=HEADERS, data=json.dumps(patient_resource))
        if update_response.status_code == 200:
            logging.info('Identifier appended successfully.')
        else:
            logging.error(f'Failed to append identifier: {update_response.status_code} {update_response.text}')
    else:
        logging.error(f'Failed to retrieve patient for updating: {response.status_code} {response.text}')

def downgrade():
    # Defines downgrading function ran on downgrade command
    response = requests.get(f'{FHIR_SERVER_URL}/Patient/{PATIENT_ID}', headers=HEADERS)
    if response.status_code == 200:
        patient_resource = response.json()
        if 'identifier' in patient_resource:
            patient_resource['identifier'] = [id for id in patient_resource['identifier'] if id['value'] != '12345']
            update_response = requests.put(f'{FHIR_SERVER_URL}/Patient/{PATIENT_ID}', headers=HEADERS, data=json.dumps(patient_resource))
            if update_response.status_code == 200:
                logging.info('Identifier deleted successfully.')
            else:
                logging.error(f'Failed to delete identifier: {update_response.status_code} {update_response.text}')
        else:
            logging.info('No identifier to delete.')
    else:
        logging.error(f'Failed to retrieve patient for updating: {response.status_code} {response.text}')
