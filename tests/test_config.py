import os
import unittest
from unittest import mock

from blockclock_backend.config import Config


class ConfigTests(unittest.TestCase):
    def test_health_port_default(self):
        with mock.patch.dict(os.environ, {"BITCOIN_SOURCE": "mock"}, clear=True):
            config = Config.from_env()
        self.assertEqual(config.health_port, 8080)

    def test_health_port_zero_disables(self):
        with mock.patch.dict(
            os.environ, {"BITCOIN_SOURCE": "mock", "HEALTH_PORT": "0"}, clear=True
        ):
            config = Config.from_env()
        self.assertIsNone(config.health_port)

    def test_health_port_empty_disables(self):
        with mock.patch.dict(
            os.environ, {"BITCOIN_SOURCE": "mock", "HEALTH_PORT": ""}, clear=True
        ):
            config = Config.from_env()
        self.assertIsNone(config.health_port)

    def test_health_port_custom(self):
        with mock.patch.dict(
            os.environ, {"BITCOIN_SOURCE": "mock", "HEALTH_PORT": "9090"}, clear=True
        ):
            config = Config.from_env()
        self.assertEqual(config.health_port, 9090)
