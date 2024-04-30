# Migration script generated for test_migration_0
# Current version: 5c929f8e-bd11-4283-9603-40613839d23a
# Previous version: None
# Add your migration code here
from functools import wraps
from datetime import datetime
from flask import Blueprint, jsonify, request

from isacc_messaging.audit import audit_entry
from isacc_messaging.models.isacc_patient import IsaccPatient as Patient

base_blueprint = Blueprint('base', __name__, cli_group=None)

@base_blueprint.route('/')
def root():
    return {'ok': True}

def upgrade():
    print("upgrade")
    """Set the active parameter to false based on provided patient id"""
    patient_id = 1953

    json_patient = Patient.get_patient_by_id(patient_id)
    patient = Patient(json_patient)
    patient.active = True
    patient.persist()
    audit_entry(
        f"Patient {patient_id} active set to true",
        level='info'
    )

def downgrade():
    print("downgrade")
    """Set the active parameter to false based on provided patient id"""
    patient_id = 1953

    json_patient = Patient.get_patient_by_id(patient_id)
    patient = Patient(json_patient)
    patient.active = False
    patient.persist()
    audit_entry(
        f"Patient {patient_id} active set to false",
        level='info'
    )
