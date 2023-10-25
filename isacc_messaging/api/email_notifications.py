from flask import current_app

from isacc_messaging.models.email import send_email
from isacc_messaging.models.isacc_patient import IsaccPatient as Patient


def send_message_received_notification(recipients: list, patient: Patient):
    subject = current_app.config.get('ISACC_NOTIFICATION_EMAIL_SUBJECT', 'New message received')
    query = f"sof_client_id=MESSAGING&patient={patient.id}"
    link_url = f'{current_app.config.get("ISACC_APP_URL")}/target?{query}'
    user_ids = patient.identifier and [i for i in patient.identifier if i.system == "http://isacc.app/user-id"] or None
    user_id = user_ids[0].value if user_ids else "no ID assigned"
    msg = f"ISACC received a message from ISACC recipient ({user_id})."
    link = f"Go to {link_url} to view it."
    text = '\n'.join((msg, link))
    html = f"""\
        <html>
          <head></head>
          <body>
            <p>{msg}
            <br><br>
               Go to <a href="{link_url}">ISACC</a> to view it.
            </p>
          </body>
        </html>
        """

    send_email(
        recipient_emails=recipients,
        subject=subject,
        text=text,
        html=html,
    )


