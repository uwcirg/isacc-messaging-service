from datetime import datetime, timedelta
from fhirclient.models.fhirdate import FHIRDate


def test_patient_datetime_extension(patient):
    url = "http://example.com/datetime"
    value = FHIRDate(datetime.now().isoformat())
    patient.set_extension(url=url, value=value.isostring, attribute="valueDateTime")
    assert len(patient.extension) == 1
    assert patient.extension[0].url == url
    assert patient.extension[0].valueDateTime.isostring == value.isostring


def test_patient_add_extension(patient):
    url = "http://example.com/no-dups"
    value = datetime.now().isoformat()

    patient.set_extension(url=url, value=value, attribute="valueDateTime")
    assert len(patient.extension) == 1
    assert patient.extension[0].url == url
    assert patient.extension[0].valueDateTime.origval == value

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
