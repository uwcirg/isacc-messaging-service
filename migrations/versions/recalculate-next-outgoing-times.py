# Migration script generated for recalculate-next-outgoing-times
revision = '17f3b60d-0777-4d0e-bb32-82e670b573a7'
down_revision = 'None'

import logging
from isacc_messaging.models.fhir import next_in_bundle
from isacc_messaging.models.isacc_patient import IsaccPatient as Patient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def upgrade():
    # iterate over active patients; confirm/set next-outgoing extension
    active_patients = Patient.active_patients()
    for json_patient in next_in_bundle(active_patients):
        patient = Patient(json_patient)
        patient.mark_next_outgoing(persist_on_change=True)
    logging.info('corrected next-outgoing-times')


def downgrade():
    # Nothing to undo
    logging.info('downgraded')

