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

    def test_price_venues_from_env(self):
        env = {
            "BITCOIN_SOURCE": "mock",
            "PRICE_COINBASE_URL": "https://coinbase.example/spot",
            "PRICE_KRAKEN_URL": "https://kraken.example/ticker",
            "PRICE_BITSTAMP_URL": "",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            config = Config.from_env()
        names = [name for name, _, _ in config.price_venues]
        self.assertEqual(names, ["coinbase", "kraken"])
        self.assertEqual(config.price_venues[0][2], "data.amount")
        self.assertEqual(config.price_venues[1][2], "result.XXBTZUSD.c.0")

    def test_price_venue_skipped_when_unset(self):
        with mock.patch.dict(os.environ, {"BITCOIN_SOURCE": "mock"}, clear=True):
            config = Config.from_env()
        self.assertEqual(config.price_venues, ())
