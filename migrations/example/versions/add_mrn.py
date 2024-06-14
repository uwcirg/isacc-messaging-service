import requests
import json
import logging
import os
import sys

# Migration script generated for adding MRNs to Patient resources
revision = 'c5a1c49e-8efb-4610-b9d3-f59f98541f16'
down_revision = 'd5a1c49e-8efb-4610-b9d3-f59f98541f16'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the FHIR server base URL
FHIR_SERVER_URL = os.getenv('FHIR_URL')

# Headers for FHIR requests
HEADERS = {
    'Content-Type': 'application/fhir+json'
}

# Mock patient to MRN map
patient_mrn_map = [
    {"PAT_ID": "12345", "MRN": "U6789012"},
    {"PAT_ID": "67890", "MRN": "U3456789"}
]

def upgrade():
    for record in patient_mrn_map:
        pat_id = record['PAT_ID']
        mrn = record['MRN']
        add_mrn_to_patient(pat_id, mrn)

def add_mrn_to_patient(pat_id, mrn):
    # Fetch the existing patient resource
    response = requests.get(f'{FHIR_SERVER_URL}/Patient',params={"identifier": f'uwDAL_Clarity|{pat_id}'}, headers=HEADERS)

    if response.status_code == 200:
        patients = response.json().get('entry', [])
        if len(patients) > 1:
            logging.error(f'Multiple patients found with PAT_ID {pat_id}. Halting the upgrade process.')
            sys.exit(1)
        elif len(patients) == 1:
            patient_resource = patients[0]['resource']
            # Add the new MRN identifier
            patient_resource['identifier'].append({
                "system": "urn:oid:1.2.3.4.5.6.7.8.9.10.11.12.13",
                "value": mrn
            })
            # Update the patient resource
            update_response = requests.put(f"{FHIR_SERVER_URL}/Patient/{patient_resource['id']}", headers=HEADERS, data=json.dumps(patient_resource))
            if update_response.status_code in [200, 201]:
                logging.info(f'Successfully updated Patient {pat_id} with MRN {mrn}.')
            else:
                logging.error(f'Failed to update Patient {pat_id}: {update_response.status_code} {update_response.text}')
        else:
            logging.error(f'No patient found with PAT_ID {pat_id}.')
    else:
        logging.error(f'Failed to fetch patient {pat_id}: {response.status_code} {response.text}')

def downgrade():
    for record in patient_mrn_map:
        pat_id = record['PAT_ID']
        mrn = record['MRN']
        remove_mrn_from_patient(pat_id, mrn)

def remove_mrn_from_patient(pat_id, mrn):
    # Fetch the existing patient resource
    response = requests.get(f'{FHIR_SERVER_URL}/Patient?identifier=uwDAL_Clarity|{pat_id}', headers=HEADERS)
    if response.status_code == 200:
        patients = response.json().get('entry', [])
        if len(patients) > 1:
            logging.error(f'Multiple patients found with PAT_ID {pat_id}. Halting the downgrade process.')
            sys.exit(1)
        elif len(patients) == 1:
            patient_resource = patients[0]['resource']
            # Remove the MRN identifier
            patient_resource['identifier'] = [id for id in patient_resource['identifier'] if id['value'] != mrn]
            # Update the patient resource
            update_response = requests.put(f"{FHIR_SERVER_URL}/Patient/{patient_resource['id']}", headers=HEADERS, data=json.dumps(patient_resource))
            if update_response.status_code in [200, 201]:
                logging.info(f'Successfully removed MRN {mrn} from Patient {pat_id}.')
            else:
                logging.error(f'Failed to update Patient {pat_id}: {update_response.status_code} {update_response.text}')
        else:
            logging.error(f'No patient found with PAT_ID {pat_id}.')
    else:
        logging.error(f'Failed to fetch patient {pat_id}: {response.status_code} {response.text}')

if __name__ == "__main__":
    # Run the upgrade function
    upgrade()
