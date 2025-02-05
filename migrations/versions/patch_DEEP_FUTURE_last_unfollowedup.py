# Migration script generated for patch_DEEP_FUTURE_last_unfollowedup
revision = '7542b481-21cb-483c-b72a-6c1502375a65'
down_revision = '17f3b60d-0777-4d0e-bb32-82e670b573a7'

import logging
from isacc_messaging.models.fhir import next_in_bundle
from isacc_messaging.models.isacc_fhirdate import (
    IsaccFHIRDate as FHIRDate,
    DEEP_FUTURE,
)
from isacc_messaging.models.isacc_patient import (
    IsaccPatient as Patient,
    LAST_UNFOLLOWEDUP_URL,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def upgrade():
    # Passed up the DEEP_FUTURE date used on patients w/o pending outgoing
    # value; corrected in PR #77, but need to migrate any existing patients
    # with expired value in their extension.
    obsolete_DEEP_FUTURE = FHIRDate("2025-01-01T00:00:00Z")
    active_patients = Patient.active_patients()
    for json_patient in next_in_bundle(active_patients):
        patient = Patient(json_patient)
        if patient.get_extension(LAST_UNFOLLOWEDUP_URL, "valueDateTime") != obsolete_DEEP_FUTURE:
            continue
        patient.mark_followup_extension(persist_on_change=True)
        logging.info(f"migration corrected {patient.id} {LAST_UNFOLLOWEDUP_URL}") 
    logging.info("migration complete")


def downgrade():
    # No value in reverting
    print('downgraded')

