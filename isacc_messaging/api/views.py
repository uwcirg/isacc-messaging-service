import logging

from flask import Blueprint, jsonify, request

import isacc_messaging
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
    isacc_messaging.audit.audit_entry(
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
    isacc_messaging.audit.audit_entry(
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
        stack = traceback.extract_statck()
        trc = "Traceback (most recent call last):\n"
        stackstr = trc + "-->".join(traceback.format_list(stack))
        if exc is not None:
            stackstr += "  " + traceback.format_exc().lstrip(trc)
        isacc_messaging.audit.audit_entry(
            f"on_twilio_message_received generated: {stackstr}",
            level="error")
        return stackstr, 500
    if result is not None:
        isacc_messaging.audit.audit_entry(
            f"on_twilio_message_received generated error {result}",
            level='error')
        return result, 500
    return '', 204


@base_blueprint.route("/sms-handler", methods=['GET','POST'])
def incoming_sms_handler():
    isacc_messaging.audit.audit_entry(
        f"Received call to /sms-handler webhook (not desired)",
        extra={'request.values': dict(request.values)},
        level='warn'
    )
    return '', 204


@base_blueprint.cli.command("execute_requests")
def execute_requests_cli():
    result = execute_requests()

    if result is not None:
        raise Exception(result)


@base_blueprint.route("/execute_requests", methods=['POST'])
def execute_requests_route():
    result = execute_requests()

    if result is not None:
        return result, 500
    return '', 204


def execute_requests():
    successes, errors = IsaccRecordCreator().execute_requests()

    if len(successes) > 0:
        isacc_messaging.audit.audit_entry(
            f"Successfully executed CommunicationRequest resources: {', '.join(successes)}",
            level='info'
        )
    if len(errors) > 0:
        error_list = '\n'.join([f"ID: {c['id']}, Error: {c['error']}" for c in errors])
        isacc_messaging.audit.audit_entry(
            "Execution failed for CommunicationRequest resources:",
            extra={'failed_resources': error_list},
            level='error'
        )
        return f"Execution failed for CommunicationRequest resources:\n{error_list}"
