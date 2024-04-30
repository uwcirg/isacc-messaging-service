# Migration script generated for test_migration_1
# Current version: 6c929f8e-bd11-4283-9603-40613839d23a
# Previous version: 5c929f8e-bd11-4283-9603-40613839d23a
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
    """Set the active parameter to false based on provided patient id"""
    patient_id = 1964
    print("upgrade")

    json_patient = Patient.get_patient_by_id(patient_id)
    patient = Patient(json_patient)
    patient.active = True
    patient.persist()
    audit_entry(
        f"Patient {patient_id} active set to true",
        level='info'
    )

def downgrade():
    """Set the active parameter to false based on provided patient id"""
    patient_id = 1964
    print("downgrade")

    json_patient = Patient.get_patient_by_id(patient_id)
    patient = Patient(json_patient)
    patient.active = False
    patient.persist()
    audit_entry(
        f"Patient {patient_id} active set to false",
        level='info'
    )
