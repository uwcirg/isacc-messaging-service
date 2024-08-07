"""Default configuration

Use env var to override
"""
import os
import redis

SERVER_NAME = os.getenv("SERVER_NAME")
SECRET_KEY = os.getenv("SECRET_KEY")
# URL scheme to use outside of request context
PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", 'http')
FHIR_URL = os.getenv("FHIR_URL")
SESSION_TYPE = os.getenv("SESSION_TYPE", 'redis')
SESSION_REDIS = redis.from_url(os.getenv("SESSION_REDIS", "redis://127.0.0.1:6379"))

REQUEST_CACHE_URL = os.environ.get('REQUEST_CACHE_URL', 'redis://localhost:6379/0')
REQUEST_CACHE_EXPIRE = 24 * 60 * 60  # 24 hours

LOGSERVER_TOKEN = os.getenv('LOGSERVER_TOKEN')
LOGSERVER_URL = os.getenv('LOGSERVER_URL')

# NB log level hardcoded at INFO for logserver
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG').upper()

VERSION_STRING = os.getenv("VERSION_STRING")

# isacc app variables
TWILIO_WEBHOOK_CALLBACK = os.getenv("TWILIO_WEBHOOK_CALLBACK")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
ML_SERVICE_ADDRESS = os.getenv("ML_SERVICE_ADDRESS")

ISACC_NOTIFICATION_EMAIL_SENDER_ADDRESS = os.getenv("ISACC_NOTIFICATION_EMAIL_SENDER_ADDRESS")
ISACC_NOTIFICATION_EMAIL_PASSWORD = os.getenv("ISACC_NOTIFICATION_EMAIL_PASSWORD")
ISACC_NOTIFICATION_EMAIL_SENDER_NAME = os.getenv("ISACC_NOTIFICATION_EMAIL_SENDER_NAME", 'ISACC Notifications')
ISACC_NOTIFICATION_EMAIL_SUBJECT = os.getenv("ISACC_NOTIFICATION_EMAIL_SUBJECT", 'New message received')
ISACC_SUPPORT_EMAIL = os.getenv("ISACC_SUPPORT_EMAIL", "isacc-support@cirg.uw.edu")
MAIL_SUPPRESS_SEND = os.getenv("MAIL_SUPPRESS_SEND", 'false').lower() == 'true'
ISACC_APP_URL = os.getenv("ISACC_APP_URL")
EMAIL_PORT = os.getenv("EMAIL_PORT", 465)
EMAIL_SERVER = os.getenv("EMAIL_SERVER", "smtp.gmail.com")
