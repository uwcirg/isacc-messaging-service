from functools import wraps
import click
import logging
from datetime import datetime
from time import sleep
from flask import Blueprint, jsonify, request
from flask import current_app
from flask.cli import with_appcontext
from twilio.request_validator import RequestValidator

from isacc_messaging.api.isacc_record_creator import IsaccRecordCreator
from isacc_messaging.audit import audit_entry
from isacc_messaging.exceptions import IsaccTwilioSIDnotFound
from isacc_messaging.robust_request import serialize_request, queue_request, pop_request

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
def message_status_update(callback_req=None, attempt_count=0):
    """Registered callback for Twilio to transmit updates

    As Twilio occasionally hits this callback prior to local data being
    available, it is also called subsequently from a job queue.  The
    parameters are only defined in the retry state.

    :param req: request from a job queue
    :param attempt_count: the number of failed attemts thus far, only
        defined from job queue
    """
    use_request = request
    if callback_req:
        use_request = callback_req

    audit_entry(
        f"Call to /MessageStatus webhook",
        extra={'use_request.values': dict(use_request.values)},
        level='debug'
    )

    record_creator = IsaccRecordCreator()
    try:
        record_creator.on_twilio_message_status_update(use_request.values)
    except Exception as ex:
        audit_entry(
            f"on_twilio_message_status_update generated error {ex}",
            level='error'
        )
        # Couldn't locate the message, most likely means twilio was quicker
        # to call back, than HAPI could persist and find.  Push to REDIS
        # for another attempt later
        if isinstance(ex, IsaccTwilioSIDnotFound):
            req = serialize_request(use_request, attempt_count=attempt_count)
            queue_request(req)

        return str(ex), 200
    return '', 204


def validate_twilio_request(f):
    """Validates that incoming requests genuinely originated from Twilio"""
    @wraps(f)
    def twilio_validation_decorated(*args, **kwargs):
        validator = RequestValidator(current_app.config.get('TWILIO_AUTH_TOKEN'))
        # Validate the request is from Twilio using its
        # URL, POST data, and X-TWILIO-SIGNATURE header
        request_valid = validator.validate(
            request.url,
            request.form,
            request.headers.get('X-TWILIO-SIGNATURE', ''))

        if not request_valid:
            audit_entry(
                f"sms request not from Twilio",
                extra={'request.values': dict(request.values)},
                level='error'
            )
            return '', 403
        return f(*args, **kwargs)
    return twilio_validation_decorated


@base_blueprint.route("/sms", methods=['GET','POST'])
@validate_twilio_request
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
        # Unexpected error
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
        return stackstr, 200
    if result is not None:
        # Occurs when message is incoming from unknown phone
        # or request is coming from a subscribed phone number, but
        # internal logic renders it invalid
        audit_entry(
            f"on_twilio_message_received generated error {result}",
            level='error')
        return result, 200
    return '', 204


@base_blueprint.route("/sms-handler", methods=['GET','POST'])
@validate_twilio_request
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


@base_blueprint.cli.command("retry_requests")
@with_appcontext
def retry_requests():
    """Look for any failed requests and retry now"""
    while True:
        failed_request = pop_request()
        if not failed_request:
            break

        # Only expecting one route at this time
        if (
                failed_request.url.endswith("/MessageStatus") and
                failed_request.method.upper() == 'POST'):
            with current_app.test_request_context():
                response, response_code = message_status_update(
                    failed_request, failed_request.attempt_count + 1)
                if response_code != 204:
                    sleep(1)  # give system a moment to catch up before retry

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
    # this was a 1 and done migration method.  disable for now
    raise click.ClickException(
        "DISABLED: unsafe to run as this will now undo any user marked "
        "read messages via "
        "https://github.com/uwcirg/isacc-messaging-client-sof/pull/85")
    from isacc_messaging.models.fhir import next_in_bundle
    from isacc_messaging.models.isacc_patient import IsaccPatient as Patient
    active_patients = Patient.active_patients()
    for json_patient in next_in_bundle(active_patients):
        patient = Patient(json_patient)
        patient.mark_next_outgoing(persist_on_change=not dry_run)
        patient.mark_followup_extension(persist_on_change=not dry_run)


@base_blueprint.cli.command("maintenance-reinstate-all-patients")
def update_patient_active():
    """Iterate through all patients, activate all of them"""
    from isacc_messaging.models.fhir import next_in_bundle
    from isacc_messaging.models.isacc_patient import IsaccPatient as Patient
    all_patients = Patient.all_patients()
    for json_patient in next_in_bundle(all_patients):
        patient = Patient(json_patient)
        patient.active = True
        patient.persist()
        audit_entry(
            f"Patient {patient.id} active set to true",
            level='info'
        )


@base_blueprint.cli.command("maintenance-add-telecom-period-start-all-patients")
def update_patient_telecom():
    """Iterate through patients, add telecom start period to all of them"""
    from isacc_messaging.models.fhir import next_in_bundle
    from isacc_messaging.models.isacc_patient import IsaccPatient as Patient
    import fhirclient.models.period as period
    from isacc_messaging.models.isacc_fhirdate import IsaccFHIRDate as FHIRDate
    patients_without_telecom_period = Patient.all_patients()
    new_period = period.Period()
    # Get the current time in UTC
    current_time = datetime.utcnow()
    # Format the current time as per the required format
    formatted_time = current_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    new_period.start = FHIRDate(formatted_time)
    for json_patient in next_in_bundle(patients_without_telecom_period):
        patient = Patient(json_patient)
        if patient.telecom:
            for telecom_entry in patient.telecom:
                if telecom_entry.system.lower() == "sms" and not telecom_entry.period:
                    telecom_entry.period = new_period
                    patient.persist()
                    audit_entry(
                        f"Patient {patient.id} active telecom period set to start now",
                        level='info'
                    )


@base_blueprint.cli.command("deactivate_patient")
@click.argument('patient_id')
def deactivate_patient(patient_id):
    """Set the active parameter to false based on provided patient id"""
    from isacc_messaging.models.isacc_patient import IsaccPatient as Patient
    json_patient = Patient.get_patient_by_id(patient_id)
    patient = Patient(json_patient)
    patient.active = False
    patient.persist()
    audit_entry(
        f"Patient {patient_id} active set to false",
        level='info'
    )
