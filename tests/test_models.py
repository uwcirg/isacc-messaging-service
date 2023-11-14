import copy
from datetime import datetime, timedelta
import json
import os

from pytest import fixture

from isacc_messaging.api.email_notifications import assemble_unresponded_email
from isacc_messaging.models.isacc_fhirdate import IsaccFHIRDate as FHIRDate
from isacc_messaging.models.isacc_patient import IsaccPatient as Patient
from isacc_messaging.models.isacc_practitioner import IsaccPractitioner as Practitioner


def load_jsondata(datadir, filename):
    """keep json files used by this test module in like named directory"""
    with open(os.path.join(datadir, filename), "r") as jsonfile:
        data = json.load(jsonfile)
    return data


@fixture
def patient_69(datadir):
    return load_jsondata(datadir, "patient_69.json")


@fixture
def patient_218(datadir):
    return load_jsondata(datadir, "patient_218.json")


@fixture
def practitioner_57(datadir):
    return load_jsondata(datadir, "practitioner_57.json")


def test_patient_datetime_extension(patient):
    url = "http://example.com/datetime"
    value = FHIRDate(datetime.now().isoformat())
    patient.set_extension(url=url, value=value.isostring, attribute="valueDateTime")
    assert len(patient.extension) == 1
    assert patient.extension[0].url == url
    assert patient.extension[0].valueDateTime.isostring == value.isostring


def test_patient_add_extension(patient):
    url = "http://example.com/no-dups"
    value = datetime.now().astimezone()

    patient.set_extension(url=url, value=value.isoformat(), attribute="valueDateTime")
    assert len(patient.extension) == 1
    assert patient.extension[0].url == url
    assert patient.extension[0].valueDateTime.origval == value.isoformat()

    # confirm specialized class (with working ==) cast works
    extension = patient.get_extension(url=url, attribute="valueDateTime")
    assert extension == value

    # confirm second add with same url replaces first value
    tomorrow = (datetime.now() + timedelta(days=1)).isoformat()

    patient.set_extension(url=url, value=tomorrow, attribute="valueDateTime")
    assert len(patient.extension) == 1
    assert patient.extension[0].url == url
    assert patient.extension[0].valueDateTime.origval == tomorrow


def test_patient_multiple_extensions(patient):
    url1 = "http://example.com/1"
    val1 = 10

    url2 = "http://example.com/2"
    val2 = "5 units"

    patient.set_extension(url=url1, value=val1, attribute="valueInteger")
    patient.set_extension(url=url2, value=val2, attribute="valueString")

    assert len(patient.extension) == 2

    first = [i for i in patient.extension if i.url == url1]
    assert len(first) == 1
    assert first[0].valueInteger == val1

    second = [i for i in patient.extension if i.url == url2]
    assert len(second) == 1
    assert second[0].valueString == val2


def test_prac_email(practitioner_57):
    prac = Practitioner(practitioner_57)
    assert prac.email_address == "mcjustin+isaccuserrmcr@uw.edu"


def test_unresponded_email_content(patient_69, patient_218, practitioner_57, app_context):
    p69 = Patient(patient_69)
    p218 = Patient(patient_218)
    practitioner = Practitioner(practitioner_57)

    # mock a third Patient for whom this practitioner is not the general
    p_other = copy.deepcopy(patient_218)
    p_other["generalPractitioner"][0]["reference"] = "Practitioner/10"
    p3 = Patient(p_other)

    parts = assemble_unresponded_email(practitioner, patients=[p3, p69, p218])
    assert "subject" in parts
    assert "html" in parts
    assert "text" in parts
    assert "There are 2 unanswered reply/ies for those who you are the primary author" in parts["text"]
    assert "There are 1 unanswered reply/ies for those whom you are following" in parts["html"]


def test_FHIRDate_compare():
    n = datetime.now().astimezone()
    dt1 = FHIRDate(n.isoformat())
    dt2 = FHIRDate(n.isoformat())

    assert dt1 == dt2


def test_FHIRDate_compare_to_dt():
    n = datetime.now().astimezone()
    dt1 = FHIRDate(n.isoformat())
    assert dt1 == n

    # confirm microseconds aren't considered
    n_no_micro = n.replace(microsecond=0)
    assert n != n_no_micro
    assert dt1 == n_no_micro


def test_FHIRDate_str():
    n = datetime.now().astimezone().replace(microsecond=0)
    dt1 = FHIRDate(n.isoformat())
    # some versions of datetime use tz offset rather than `Z`
    assert str(dt1) == n.isoformat().replace("+00:00", "Z")
