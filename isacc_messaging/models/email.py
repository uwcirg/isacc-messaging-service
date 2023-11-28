"""Module for email utility functions"""
from email import utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app
import smtplib
import ssl

from isacc_messaging.audit import audit_entry


def send_email(recipient_emails: list, subject, text, html):
    """Utility function to send given email"""
    port = current_app.config.get('EMAIL_PORT')  # For SSL
    email_server = current_app.config.get('EMAIL_SERVER')
    sender_email = current_app.config.get('ISACC_NOTIFICATION_EMAIL_SENDER_ADDRESS')
    app_password = current_app.config.get('ISACC_NOTIFICATION_EMAIL_PASSWORD')
    sender_name = current_app.config.get('ISACC_NOTIFICATION_EMAIL_SENDER_NAME')

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender_name
    msg.add_header("To", ' '.join(recipient_emails))
    msg.add_header("List-Unsubscribe", f"{current_app.config.get('ISACC_APP_URL')}/unsubscribe")
    msg.add_header("Date", utils.format_datetime(utils.localtime()))
    msg.add_header("Message-Id", utils.make_msgid())

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
            server.sendmail(sender_name, recipient_emails, msg.as_string())
            audit_entry(
                f"Email notification sent",
                extra={
                    'email_message': msg.as_string(),
                    'recipients': recipient_emails
                },
                level='info'
            )
    except Exception as e:
        audit_entry(
            f"Email notification could not be sent",
            extra={
                'recipient_emails': ' '.join(recipient_emails),
                'exception': str(e)},
            level='error'
        )
        # present stack for easier debugging
        raise e
