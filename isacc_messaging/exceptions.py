"""Module to define exceptions used by isacc_messaging."""

class IsaccTwilioSIDnotFound(Exception):
    """Raised when Twilio calls with SID that can't be found"""
    pass


class IsaccRequestRetriesExhausted(Exception):
    """Raised when max retries have been tried w/o success"""
    pass
