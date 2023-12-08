import click
import logging

from flask import Blueprint, jsonify, request

from isacc_messaging.api.isacc_record_creator import IsaccRecordCreator
from isacc_messaging.audit import audit_entry

base_blueprint = Blueprint('base', __name__, cli_group=None)


@base_blueprint.route('/')
def root():
    return {'ok': True}


@base_blueprint.route('/auditlog', methods=('POST',))
def auditlog_addevent():
    """Add event to audit log

    API for client applications to add any event to the audit log.  The message
    will land in the same audit log as any auditable internal event, including
    recording the authenticated user making the call.

    Returns a json friendly message, i.e. {"message": "ok"} or details on error
    ---
    operationId: auditlog_addevent
    tags:
      - audit
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        schema:
          id: message
          required:
            - message
          properties:
            user:
              type: string
              description: user identifier, such as email address or ID
            patient:
              type: string
              description: patient identifier (if applicable)
            level:
              type: string
              description: context such as "error", default "info"
            message:
              type: string
              description: message text
    responses:
      200:
        description: successful operation
        schema:
          id: response_ok
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "ok"
      401:
        description: if missing valid OAuth token
    security:
      - ServiceToken: []

    """
    body = None
    if request.data:
        body = request.get_json()

    if not body:
        return jsonify(message="Missing JSON data"), 400

    message = body.pop('message', None)
    level = body.pop('level', 'info')
    if not hasattr(logging, level.upper()):
        return jsonify(message="Unknown logging `level`: {level}"), 400
    if not message:
        return jsonify(message="missing required 'message' in post"), 400

    extra = {k: v for k, v in body.items()}
    audit_entry(message, level, extra)
    return jsonify(message='ok')


@base_blueprint.route("/MessageStatus", methods=['POST'])
def message_status_update():
    audit_entry(
        f"Call to /MessageStatus webhook",
        extra={'request.values': dict(request.values)},
        level='debug'
    )

    record_creator = IsaccRecordCreator()
    result = record_creator.on_twilio_message_status_update(request.values)
    if result is not None:
        return result, 500
    return '', 204


@base_blueprint.route("/sms", methods=['GET','POST'])
def incoming_sms():
    audit_entry(
        f"Call to /sms webhook",
        extra={'request.values': dict(request.values)},
        level='debug'
    )
    try:
        record_creator = IsaccRecordCreator()
        result = record_creator.on_twilio_message_received(request.values)
    except Exception as e:
        import traceback, sys
        exc = sys.exc_info()[0]
        stack = traceback.extract_stack()
        trc = "Traceback (most recent call last):\n"
        stackstr = trc + "-->".join(traceback.format_list(stack))
        if exc is not None:
            stackstr += "  " + traceback.format_exc().lstrip(trc)
        audit_entry(
            f"on_twilio_message_received generated: {stackstr}",
            level="error")
        return stackstr, 500
    if result is not None:
        audit_entry(
            f"on_twilio_message_received generated error {result}",
            level='error')
        return result, 500
    return '', 204


@base_blueprint.route("/sms-handler", methods=['GET','POST'])
def incoming_sms_handler():
    audit_entry(
        f"Received call to /sms-handler webhook (not desired)",
        extra={'request.values': dict(request.values)},
        level='warn'
    )
    return '', 204


@base_blueprint.cli.command("execute_requests")
def execute_requests_cli():
    execute_requests()


@base_blueprint.route("/execute_requests", methods=['POST'])
def execute_requests_route():
    result = execute_requests()
    return str(result), 204


def execute_requests():
    successes, errors = IsaccRecordCreator().execute_requests()

    success_list = ""
    error_list = ""

    if len(successes) > 0:
        success_list = '\n'.join([f"ID: {c['id']}, Status: {c['status']}" for c in successes])
        audit_entry(
            f"Successfully executed CommunicationRequest resources",
            extra={'successful_resources': success_list},
            level='info'
        )
    if len(errors) > 0:
        error_list = '\n'.join([f"ID: {c['id']}, Error: {c['error']}" for c in errors])
        audit_entry(
            "Execution failed for CommunicationRequest resources",
            extra={'failed_resources': error_list},
            level='error'
        )
    return "\n".join([
        f"Execution succeeded for CommunicationRequest resources:\n{success_list}",
        f"Execution failed for CommunicationRequest resources:\n{error_list}"
    ])


@base_blueprint.cli.command("send-system-emails")
@click.argument("category", required=True)
@click.option("--dry-run", is_flag=True, default=False, help="Simulate execution; generate but don't send email")
@click.option("--include-test-patients", is_flag=True, default=False, help="Include test patients")
def send_system_emails(category, dry_run, include_test_patients):
    from isacc_messaging.api.email_notifications import generate_outgoing_counts_emails, generate_unresponded_emails
    if category == 'unresponded':
        generate_unresponded_emails(dry_run, include_test_patients)
    elif category == 'outgoing':
        generate_outgoing_counts_emails(dry_run, include_test_patients)
    else:
        click.echo(f"unsupported category: {category}")


@base_blueprint.cli.command("maintenance-update-patient-extensions")
@click.option("--dry-run", is_flag=True, default=False, help="Simulate execution; don't persist to FHIR store")
def update_patient_extensions(dry_run):
    """Iterate through active patients, update any stale/missing extensions"""
    from isacc_messaging.models.fhir import next_in_bundle
    from isacc_messaging.models.isacc_patient import IsaccPatient as Patient
    active_patients = Patient.active_patients()
    for json_patient in next_in_bundle(active_patients):
        patient = Patient(json_patient)
        patient.mark_next_outgoing(persist_on_change=not dry_run)
        patient.mark_followup_extension(persist_on_change=not dry_run)


@base_blueprint.cli.command("maintenance-reinstate-all-patients")
def update_patient_params():
    """Iterate through all patients, update any the parameter values for all of them"""
    from isacc_messaging.models.fhir import next_in_bundle
    from isacc_messaging.models.isacc_patient import IsaccPatient as Patient
    all_patients = Patient.all_patients()
    for json_patient in next_in_bundle(all_patients):
        patient = Patient(json_patient)
        patient.active = True
        patient.persist()


@base_blueprint.cli.command("deactivate_patient")
@click.argument('patient_id')
def deactivate_patient(patient_id):
    """Iterate through all patients, update any the parameter values for all of them"""
    from isacc_messaging.models.fhir import next_in_bundle
    from isacc_messaging.models.isacc_patient import IsaccPatient as Patient
    all_patients = Patient.all_patients(patient_id)
    for json_patient in next_in_bundle(all_patients):
        patient = Patient(json_patient)
        if patient.id == patient_id:
            patient.active = False
            patient.persist()
            break

    audit_entry(
        f"Deactivated a patient {patient_id}",
        level='info'
    )
