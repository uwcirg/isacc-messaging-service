"""Model for email content generation and helpers"""
import click
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app
import logging
import smtplib
import ssl

from fhirclient.models.fhirdate import FHIRDate

from isacc_messaging.models.fhir import next_in_bundle
from isacc_messaging.models.isacc_patient import LAST_UNFOLLOWEDUP_URL
from isacc_messaging.models.isacc_practitioner import IsaccPractitioner as Practitioner


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


html_template = """
    <html>
      <head></head>
      <body>
        <p>{msg}
        <br><br>
           Go to <a href="{link_url}">ISACC</a> {link_suffix_text}.
        </p>
      </body>
    </html>
    """


def assemble_unresponded_email(practitioner, patients):
    """Pull together email content for given practitioner and their list of patients

    :param practitioner: Practitioner object, target of email
    :param patients: list of Patient objects for whom the practitioner is assigned,
      expected to only include those with an un-responded message
    :return: email content
    """
    patient_list_url = f'{current_app.config.get("ISACC_APP_URL")}/flag-for-my-patient?practitioner={practitioner.id}'
    oldest_primary = datetime.now().astimezone()
    oldest_secondary = oldest_primary
    primary, secondary = [], []
    for p in patients:
        moment = p.get_extension(LAST_UNFOLLOWEDUP_URL, attribute="valueDateTime").date
        if p.generalPractitioner and p.generalPractitioner[0].reference == f"Practitioner/{practitioner.id}":
            primary.append(p)
            oldest_primary = min(oldest_primary, moment)
            continue
        secondary.append(p)
        oldest_secondary = min(oldest_secondary, moment)

    subject = f"ISACC {len(patients)} day old message/s are unanswered!"
    contents = []
    if primary:
        contents.append(f"There are {len(primary)} unanswered reply/ies for those who you are the primary author.")
        contents.append(f"The oldest one is {oldest_primary} day/s old.")
    if secondary:
        contents.append(f"There are {len(secondary)} unanswered reply/ies for those whom you are following.")
        contents.append(f"The oldest one is {oldest_secondary} day/s old.")
    msg = " ".join(contents)
    contents.append(f"Click here {patient_list_url} to get to the list of these outstanding messages from these people.")
    html = html_template.format(
        msg=msg,
        link_url=patient_list_url,
        link_suffix_text="to get to the list of these outstanding messages from these people")

    return {
        "subject": subject,
        "text": " ".join(contents),
        "html": html}


def generate_unresponded_emails(dry_run):
    """Generate system emails to practitioners with counts

    :param dry_run: set true to generate but not send email

    At a scheduled time every day, this function will be triggered to generate email
    for every practitioner in the system, detailing the number of patients for which
    they have un-responded texts and how long it has been, etc.
    """
    cutoff = FHIRDate((datetime.now().astimezone() - timedelta(days=1)).isoformat())
    known_keepers = []
    known_skippers = []

    def unresponded_patients(patients):
        """helper to return only sublist of patients with qualified un-responded messages"""
        keepers = []
        for p in patients:
            if p in known_keepers:
                keepers.append(p)
                continue
            if p in known_skippers:
                continue

            last_unresponded = p.get_extension(LAST_UNFOLLOWEDUP_URL, attribute="valueDateTime")
            if last_unresponded and last_unresponded < cutoff:
                keepers.append(p)
                known_keepers.append(p)
            else:
                known_skippers.append(p)

        return keepers

    practitioners = Practitioner.active_practitioners()
    for p in next_in_bundle(practitioners):
        practitioner = Practitioner(p)
        practitioners_patients = practitioner.practitioner_patients()
        unresponded = unresponded_patients(practitioners_patients)
        if not unresponded:
            logging.debug(f"no qualifying unresponded patients for {practitioner}")
            continue

        email_bits = assemble_unresponded_email(practitioner, unresponded)
        if not dry_run:
            send_email(
                recipient_emails=[practitioner.email_address],
                subject=email_bits["subject"],
                html=email_bits["html"],
                text=email_bits["text"])
        else:
            click.echo(
                f"email to: {practitioner.email_address}\n"
                f"subject: {email_bits['subject']}\n"
                f"body: {email_bits['text']}\n\n"
                f"html: {email_bits['html']}\n\n"
            )

