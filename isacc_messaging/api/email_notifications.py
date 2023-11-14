import logging
from datetime import datetime, timedelta

import click

from flask import current_app

from isacc_messaging.models.email import send_email
from isacc_messaging.models.fhir import next_in_bundle
from isacc_messaging.models.isacc_patient import (
    IsaccPatient as Patient,
    LAST_UNFOLLOWEDUP_URL,
    NEXT_OUTGOING_URL,
)
from isacc_messaging.models.isacc_practitioner import IsaccPractitioner as Practitioner

html_template = """
    <html>
      <head></head>
      <body>
        <p>{pre_link_msg}
        <br><br>
           Go to <a href="{link_url}">ISACC</a> {link_suffix_text}.
        </p>
        <p>{post_link_msg}
        </p>
        <p><a href="{unsubscribe_link}">Click here to unsubscribe.</a></p>
      </body>
    </html>
    """


def send_message_received_notification(recipients: list, patient: Patient):
    SUPPORT_EMAIL = current_app.config.get('ISACC_SUPPORT_EMAIL')
    UNSUB_LINK = f'{current_app.config.get("ISACC_APP_URL")}/unsubscribe'
    subject = current_app.config.get('ISACC_NOTIFICATION_EMAIL_SUBJECT', 'New message received')
    query = f"sof_client_id=MESSAGING&patient={patient.id}"
    link_url = f'{current_app.config.get("ISACC_APP_URL")}/target?{query}'
    user_ids = patient.identifier and [i for i in patient.identifier if i.system == "http://isacc.app/user-id"] or None
    user_id = user_ids[0].value if user_ids else "no ID assigned"
    msg = f"ISACC received a message from ISACC recipient ({user_id})."
    link = f"Go to {link_url} to view it."
    text = '\n'.join((msg, link))
    html = html_template.format(
        pre_link_msg=msg,
        link_url=link_url,
        link_suffix_text="to view it",
        post_link_msg=(
            f'<h3><a href="mailto:{SUPPORT_EMAIL}">Send Email</a>'
            'if you have questions.</h3>'),
        unsubscribe_link=UNSUB_LINK)

    send_email(
        recipient_emails=recipients,
        subject=subject,
        text=text,
        html=html,
    )


def assemble_outgoing_counts_email(practitioner, patients):
    """Pull together email content for given practitioner and their list of patients

    :param practitioner: Practitioner object, target of email
    :param patients: list of Patient objects for whom the practitioner is assigned,
      expected to only include those with an outgoing message in the next 24 hours
    :return: email content
    """
    SUPPORT_EMAIL = current_app.config.get('ISACC_SUPPORT_EMAIL')
    UNSUB_LINK = f'{current_app.config.get("ISACC_APP_URL")}/unsubscribe'
    patient_list_url = f'{current_app.config.get("ISACC_APP_URL")}/home?sort_by=next_message&sort_direction=desc&flags=following'
    primary, secondary = [], []
    for p in patients:
        if p.generalPractitioner and p.generalPractitioner[0].reference == f"Practitioner/{practitioner.id}":
            primary.append(p)
            continue
        secondary.append(p)

    subject = f"ISACC {len(patients)} Caring Contact sending today"
    contents = []
    contents.append(f"Today Caring Contact messages will be sent to {len(primary)} recipients for")
    contents.append(f"whom you are the primary author, and {len(secondary)} for whom you are following.")
    msg = " ".join(contents)
    contents.append(f"Click here {patient_list_url} to view which of your recipients will be receiving a message.")
    contents.append("If you are not the person who should be getting these messages, contact your site lead.")
    html = html_template.format(
        pre_link_msg=msg,
        link_url=patient_list_url,
        link_suffix_text="to view which of your recipients will be receiving a message",
        post_link_msg=(
            "If you are not the person who should be getting these messages, contact "
            f'<a href="mailto:{SUPPORT_EMAIL}">your site lead</a>.'),
        unsubscribe_link=UNSUB_LINK)

    return {
        "subject": subject,
        "text": " ".join(contents),
        "html": html}


def unique_by_id_add(container, item):
    """only add item to container if the item.id is not already in container

    NB: mutates container by adding item if not already present
    """
    already_present = [i for i in container if i.id == item.id]
    if already_present:
        return
    container.add(item)


known_keepers = set()  # set of unique patient ids
known_skippers = set() # set of unique patient ids


def filter_patients(patients, filter_func):
    """helper to return only sublist of patients using filter function"""
    keepers = set()
    for p in patients:
        id = p.id
        if id in known_keepers:
            unique_by_id_add(container=keepers, item=p)
            continue
        if id in known_skippers:
            continue

        if filter_func(p):
            unique_by_id_add(container=keepers, item=p)
            known_keepers.add(id)
        else:
            known_skippers.add(id)

    return list(keepers)


def generate_outgoing_counts_emails(dry_run, include_test_patients):
    """Generate system emails to practitioners with counts

    :param dry_run: set true to generate but not send email
    :param include_test_patients: set true to include test patients

    At a scheduled time every day, this function will be triggered to generate email
    for every practitioner in the system, detailing the number of patients for which
    they have outgoing texts in the next 24 hours.
    """
    now = datetime.now().astimezone()
    cutoff = now + timedelta(days=1)
    known_keepers.clear()
    known_skippers.clear()

    def keep_patient_criteria(patient):
        """function passed to filter out which patients should be kept for this report"""
        next_outgoing = patient.get_extension(NEXT_OUTGOING_URL, attribute="valueDateTime")
        if next_outgoing and next_outgoing.date > now and next_outgoing.date < cutoff:
            return True

    practitioners = Practitioner.active_practitioners()
    for p in next_in_bundle(practitioners):
        practitioner = Practitioner(p)
        practitioners_patients = practitioner.practitioner_patients(include_test_patients=include_test_patients)
        outgoing = filter_patients(patients=practitioners_patients, filter_func=keep_patient_criteria)
        if not outgoing:
            logging.debug(f"no qualifying outgoing patients for {practitioner}")
            continue

        email_bits = assemble_outgoing_counts_email(practitioner, outgoing)
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



def assemble_unresponded_email(practitioner, patients):
    """Pull together email content for given practitioner and their list of patients

    :param practitioner: Practitioner object, target of email
    :param patients: list of Patient objects for whom the practitioner is assigned,
      expected to only include those with an un-responded message
    :return: email content
    """
    SUPPORT_EMAIL = current_app.config.get('ISACC_SUPPORT_EMAIL')
    UNSUB_LINK = f'{current_app.config.get("ISACC_APP_URL")}/unsubscribe'
    patient_list_url = f'{current_app.config.get("ISACC_APP_URL")}/home?flags=following'
    now = datetime.now().astimezone()
    oldest_primary = now
    oldest_secondary = now
    primary, secondary = [], []
    for p in patients:
        moment = p.get_extension(LAST_UNFOLLOWEDUP_URL, attribute="valueDateTime").date
        if p.generalPractitioner and p.generalPractitioner[0].reference == f"Practitioner/{practitioner.id}":
            primary.append(p)
            oldest_primary = min(oldest_primary, moment)
            continue
        secondary.append(p)
        oldest_secondary = min(oldest_secondary, moment)

    oldest_primary_days = (now - oldest_primary).days
    oldest_secondary_days = (now - oldest_secondary).days
    subject = f"ISACC {len(patients)} day old message/s are unanswered!"
    contents = []
    if primary:
        contents.append(f"There are {len(primary)} unanswered reply/ies for those who you are the primary author.")
        contents.append(f"The oldest one is {oldest_primary_days} day/s old.")
    if secondary:
        contents.append(f"There are {len(secondary)} unanswered reply/ies for those whom you are following.")
        contents.append(f"The oldest one is {oldest_secondary_days} day/s old.")
    msg = " ".join(contents)
    contents.append(f"Click here {patient_list_url} to get to the list of these outstanding messages from these people.")
    contents.append("If you are not the person who should be getting these messages, contact your site lead.")
    html = html_template.format(
        pre_link_msg=msg,
        link_url=patient_list_url,
        link_suffix_text="to get to the list of these outstanding messages from these people",
        post_link_msg=(
            "If you are not the person who should be getting these messages, contact "
            f'<a href="mailto:{SUPPORT_EMAIL}">your site lead</a>.'),
        unsubscribe_link=UNSUB_LINK)

    return {
        "subject": subject,
        "text": " ".join(contents),
        "html": html}


def generate_unresponded_emails(dry_run, include_test_patients):
    """Generate system emails to practitioners with counts

    :param dry_run: set true to generate but not send email
    :param include_test_patients: set true to include test patients

    At a scheduled time every day, this function will be triggered to generate email
    for every practitioner in the system, detailing the number of patients for which
    they have un-responded texts and how long it has been, etc.
    """
    cutoff = datetime.now().astimezone() - timedelta(days=1)
    known_keepers.clear()
    known_skippers.clear()

    def keep_patient_criteria(patient):
        """function passed to filter out which patients should be kept for this report"""
        last_unresponded = patient.get_extension(LAST_UNFOLLOWEDUP_URL, attribute="valueDateTime")
        if last_unresponded and last_unresponded.date < cutoff:
            return True

    practitioners = Practitioner.active_practitioners()
    for p in next_in_bundle(practitioners):
        practitioner = Practitioner(p)
        practitioners_patients = practitioner.practitioner_patients(include_test_patients=include_test_patients)
        unresponded = filter_patients(patients=practitioners_patients, filter_func=keep_patient_criteria)
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
