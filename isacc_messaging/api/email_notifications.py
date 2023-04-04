import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

import isacc_messaging


def send_message_received_notification(recipients: list, patient_message, patient_name):
    port = current_app.config.get('EMAIL_PORT')  # For SSL
    email_server = current_app.config.get('EMAIL_SERVER')
    email = current_app.config.get('ISACC_NOTIFICATION_EMAIL_SENDER_ADDRESS')
    subject = current_app.config.get('ISACC_NOTIFICATION_EMAIL_SUBJECT', 'New message received')
    app_password = current_app.config.get('ISACC_NOTIFICATION_EMAIL_PASSWORD')
    sender_name = current_app.config.get('ISACC_NOTIFICATION_EMAIL_SENDER_NAME')
    link_url = current_app.config.get("ISACC_APP_URL")
    text = f"ISACC received a message.\nGo to {link_url} to view it."
    html = f"""\
        <html>
          <head></head>
          <body>
            <p>ISACC received a message from {patient_name}:<br><br>
            {patient_message}
            <br><br>
               Go to <a href="{link_url}">ISACC</a> to view it.
            </p>
          </body>
        </html>
        """

    suppress_send = current_app.config.get('MAIL_SUPPRESS_SEND')
    if not suppress_send:
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
                'exception': str(e)},
            level='info'
        )
