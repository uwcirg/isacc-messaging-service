import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fhirclient.models.patient import Patient

from flask import current_app

import isacc_messaging


def send_message_received_notification(recipients: list, patient: Patient):
    port = current_app.config.get('EMAIL_PORT')  # For SSL
    email_server = current_app.config.get('EMAIL_SERVER')
    email = current_app.config.get('ISACC_NOTIFICATION_EMAIL_SENDER_ADDRESS')
    subject = current_app.config.get('ISACC_NOTIFICATION_EMAIL_SUBJECT', 'New message received')
    app_password = current_app.config.get('ISACC_NOTIFICATION_EMAIL_PASSWORD')
    sender_name = current_app.config.get('ISACC_NOTIFICATION_EMAIL_SENDER_NAME')
    query = f"sof_client_id=MESSAGING&patient={patient.id}"
    link_url = f'{current_app.config.get("ISACC_APP_URL")}/target?{query}'
    if not patient:
        isacc_messaging.audit.audit_entry(
            f"Email notification could not be sent - no patient",
            extra={'recipient_emails': ' '.join(recipients)},
            level='error'
        )
        return "Need patient"
    user_id = "no ID assigned"
    if patient.identifier and len([i for i in patient.identifier if i.system == "http://isacc.app/user-id"]) > 0:
        for i in patient.identifier:
            if i.system == "http://isacc.app/user-id":
                user_id = i.value
    text = f"ISACC received a message from ISACC recipient({user_id}).\nGo to {link_url} to view it."
    html = f"""\
        <html>
          <head></head>
          <body>
            <p>ISACC received a patient message.
            <br><br>
               Go to <a href="{link_url}">ISACC</a> to view it.
            </p>
          </body>
        </html>
        """

    send_email(
        recipient_emails=recipients,
        sender_email=email,
        sender_name=sender_name,
        app_password=app_password,
        subject=subject,
        text=text,
        html=html,
        port=port,
        email_server=email_server
    )


def send_email(recipient_emails: list, sender_email, sender_name, app_password, subject, text, html, port,
               email_server):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender_name

    # Record the MIME types of both parts - text/plain and text/html.
    part1 = MIMEText(text, 'plain')
    msg.attach(part1)

    part2 = MIMEText(html, 'html')
    msg.attach(part2)

    # Create a secure SSL context
    context = ssl.create_default_context()

    if current_app.config.get('MAIL_SUPPRESS_SEND'):
        return

    try:
        with smtplib.SMTP_SSL(email_server, port, context=context) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, recipient_emails, msg.as_string())
            isacc_messaging.audit.audit_entry(
                f"Email notification sent",
                extra={
                    'email_message': msg.as_string(),
                    'recipients': recipient_emails
                },
                level='info'
            )
    except Exception as e:
        isacc_messaging.audit.audit_entry(
            f"Email notification could not be sent",
            extra={
                'recipient_emails': ' '.join(recipient_emails),
                'exception': str(e)},
            level='error'
        )
