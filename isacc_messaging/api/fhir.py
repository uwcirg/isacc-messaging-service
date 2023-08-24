from flask import current_app
import requests

from fhirclient.models.careteam import CareTeam
from fhirclient.models.patient import Patient
from fhirclient.models.practitioner import Practitioner
from isacc_messaging.audit import audit_entry


def resolve_reference(reference_string):
    """FHIRClient includes a `resolved()` method, but has yet to implement

    :param reference_string: i.e. "Patient/2"
    :return: instantiated FHIRClient instance by fetching resource
    """
    # expand supported class list as needed
    supported_classes = {
        "CareTeam": CareTeam,
        "Patient": Patient,
        "Practitioner": Practitioner,
    }
    resource_type, id = reference_string.split('/')
    klass = supported_classes.get(resource_type)
    if klass is None:
        raise ValueError("resource_type: {resource_type} not in supported")

    result = HAPI_request('GET', resource_type, resource_id=id)
    if result is not None:
        return klass(result)
    raise IsaccNotFoundError("{reference_string} NOT FOUND")


def HAPI_request(
    method, resource_type=None, resource_id=None, resource=None, params=None
):
    """Execute HAPI request on configured system - return JSON

    :param method: HTTP verb, POST, PUT, GET, DELETE
    :param resource_type: String naming desired such as ``Patient``
    :param resource_id: Optional, used when requesting specific resource
    :param resource: FHIR resource used in PUT/POST
    :param params: Optional additional search parameters

    """
    url = current_app.config.get("FHIR_URL")
    if resource_type:
        url = url + resource_type

    if resource_id is not None:
        if not resource_type:
            raise ValueError("resource_type required when requesting by id")
        url = "/".join((url, str(resource_id)))

    VERB = method.upper()
    if VERB == "GET":
        # By default, HAPI caches search results for 60000 milliseconds,
        # meaning new patients won't immediately appear in results.
        # Disable caching until we find the need and safe use cases
        headers = {"Cache-Control": "no-cache"}
        try:
            resp = requests.get(
                url, headers=headers, params=params, timeout=30
            )
        except requests.exceptions.ConnectionError as error:
            current_app.logger.exception(error)
            raise RuntimeError(f"{url} inaccessible")
    elif VERB == "POST":
        resp = requests.post(
            url, params=params, json=resource, timeout=30
        )
    elif VERB == "PUT":
        resp = requests.put(
            url, params=params, json=resource, timeout=30
        )
    elif VERB == "DELETE":
        # Only enable deletion of resource by id
        if not resource_id:
            raise ValueError("'resource_id' required for DELETE")
        resp = requests.delete(url, timeout=30)
    else:
        raise ValueError(f"Invalid HTTP method: {method}")

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as err:
        current_app.logger.exception(err)
        audit_entry(
            f"Failed HAPI call ({method} {resource_type} {resource_id} {resource} {params}): {err}",
            extra={"tags": ["Internal", "Exception", resource_type]},
            level="error",
        )
        raise ValueError(err)

    return resp.json()

