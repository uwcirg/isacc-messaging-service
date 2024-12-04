"""Functions used for robust handling of failed requests

Basic model: a request fails.  Rather than give up, push the request
to a job queue and try again from a consumer.
"""
import json
import redis
from flask import current_app

from isacc_messaging.exceptions import IsaccRequestRetriesExhausted


def serialize_request(req, attempt_count=1, max_retries=3):
    """Given a request object, returns a serialized form

    :param req: The request object
    :param attempt_count: Increment from previous failure on each call
    :param max_retries: Maximum number of retries before giving up

    Need a serialized form of the request to push into a job queue.
    This also maintains and enforces the number of attempts doesn't
    exceed the maximum.
    """
    serialized_form = json.dumps({
        "method": req.method,
        "url": req.url,
        "headers": dict(req.headers),
        "body": req.get_data(as_text=True),
        "attempt_count": attempt_count,
        "max_retries": max_retries
    })
    if attempt_count > max_retries:
        raise IsaccRequestRetriesExhausted(serialized_form)
    return serialized_form

def queue_request(serialized_request):
    redis_client = redis.StrictRedis.from_url(current_app.config.get("REQUEST_CACHE_URL"))
    redis_client.lpush("http_request_queue", serialized_request)


def pop_request():
    redis_client = redis.StrictRedis.from_url(current_app.config.get("REQUEST_CACHE_URL"))
    return redis_client.rpop("http_request_queue")

