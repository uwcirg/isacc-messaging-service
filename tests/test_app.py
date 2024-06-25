import unittest
from isacc_messaging.app import create_app

class TestConfig:
    TESTING = True
    LOG_LEVEL = 'DEBUG'
    LOGSERVER_URL = None
    LOGSERVER_TOKEN = None
    VERSION_STRING = 'test_version'
    PREFERRED_URL_SCHEME = 'http'


class TestIsaccMessagingApp(unittest.TestCase):
    def setUp(self):
        self.app = create_app(testing=True)
        self.app.config.from_object(TestConfig)
        self.client = self.app.test_client()

    def test_app_exists(self):
        self.assertIsNotNone(self.app)

    def test_blueprints_registered(self):
        self.assertIn('base', self.app.blueprints)
        self.assertIn('migration', self.app.blueprints)

if __name__ == '__main__':
    unittest.main()
