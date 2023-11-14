from pytest import fixture

@fixture
def app():
    from isacc_messaging.app import create_app
    return create_app(testing=True)


@fixture
def app_context(app):
    with app.app_context():
        yield


@fixture
def client(app):
    with app.test_client() as c:
        yield c


@fixture
def patient():
    from isacc_messaging.models.isacc_patient import IsaccPatient as Patient
    p = Patient()
    return p
