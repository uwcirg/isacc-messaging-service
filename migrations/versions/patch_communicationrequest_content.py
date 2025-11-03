# Migration script generated for patch_communicationrequest_content
revision = 'ac2232ce-8634-43b9-93fd-385a31793d2e'
down_revision = '7542b481-21cb-483c-b72a-6c1502375a65'

import logging
from isacc_messaging.models.fhir import next_in_bundle
from isacc_messaging.models.isacc_communicationrequest import IsaccCommunicationRequest

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def upgrade():
    # Find all active CommunicationRequest resources
    params = {
        "status": "active",
        "_count": 5000
    }
    from isacc_messaging.models.fhir import HAPI_request
    bundle = HAPI_request('GET', 'CommunicationRequest', params=params)
    count = 0
    for cr_json in next_in_bundle(bundle):
        cr = IsaccCommunicationRequest(cr_json)
        # Check payload[0].contentString starts with 'Thinking of you'
        if not cr.payload or not hasattr(cr.payload[0], 'contentString'):
            continue
        content = cr.payload[0].contentString
        if not content or not content.startswith("Thinking of you"):
            continue
        new_content = (
            "Thinking of you, {name} 🙂 I'm not always available but if you need to talk to someone, "
            "you can try Vets4Warriors or ObjectiveZero for peer chat/support/advice for veterans (and their families/loved ones). "
            "Here are their links: https://vets4warriors.com/talk-to-us/ and https://www.objectivezero.org/veterans. "
            "For immediate help, the National Hotline number is 988 & press 1 and the Veterans Crisis Line text number is 838-255. -{username}"
        )
        cr.payload[0].contentString = new_content
        cr.persist()
        count += 1
        logging.info(f"Updated CommunicationRequest {cr.id}")
    logging.info(f"Migration complete. Updated {count} CommunicationRequest resources.")

def downgrade():
    # No value in reverting as this is a one-time migration
    print('downgraded (no action taken)')