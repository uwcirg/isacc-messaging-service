from pytest import fixture
from isacc_messaging.models.isacc_patient import IsaccPatient as Patient

@fixture
def app():
    from isacc_messaging.app import create_app
    return create_app(testing=True)


@fixture
def client(app):
    with app.test_client() as c:
        yield c


@fixture
def patient():
    p = Patient()
    return p
