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


@base_blueprint.route('/convert', methods=('POST',))
def convert():
    cr_id = request.form['cr']
    result = convert_communicationrequest_to_communication(cr_id)
    return result


def convert_communicationrequest_to_communication(cr_id):
    record_creator = IsaccRecordCreator()
    result = record_creator.convert_communicationrequest_to_communication(cr_id=cr_id)
    return result


@base_blueprint.route("/MessageStatus", methods=['POST'])
def message_status_update():
    record_creator = IsaccRecordCreator()
    result = record_creator.on_twilio_message_status_update(request.values)
    if result is not None:
        return ('', 204)
    return ('', 500)


@base_blueprint.route("/sms", methods=['GET','POST'])
def incoming_sms():
    record_creator = IsaccRecordCreator()
    result = record_creator.on_twilio_message_received(request.values)
    if result is not None:
        return ('', 204)
    return ('', 500)


@base_blueprint.cli.command("execute_requests")
def execute_requests_cli():
    results = IsaccRecordCreator().execute_requests()
    if results is not None:
        print(f"Successfully generated Communication resources: {', '.join([c.id for c in results])}")


@base_blueprint.route("/execute_requests", methods=['POST'])
def execute_requests_route():
    results = IsaccRecordCreator().execute_requests()
    if results is not None:
        return ('', 204)
    return ('', 500)


