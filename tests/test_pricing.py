import io
import json
import unittest
from unittest import mock

from blockclock_backend.bitcoin import DataSourceError
from blockclock_backend.pricing import ConfiguredPriceSource, Venue


def _response(payload):
    body = json.dumps(payload).encode()
    return io.BytesIO(body)


class PricingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.venues = (
            Venue("coinbase", "https://coinbase.test/spot", "data.amount"),
            Venue("kraken", "https://kraken.test/ticker", "result.XXBTZUSD.c.0"),
            Venue("bitstamp", "https://bitstamp.test/ticker", "last"),
            Venue("gemini", "https://gemini.test/ticker", "last"),
        )
        self.source = ConfiguredPriceSource(
            None, "", "", timeout=1, ttl=30, venues=self.venues
        )

    def _urlopen_for(self, mapping, fail=None):
        fail = fail or set()

        def fake(request, timeout=0):
            url = request.full_url
            for key, payload in mapping.items():
                if key in url:
                    if key in fail:
                        raise TimeoutError(f"{key} timeout")
                    cm = mock.MagicMock()
                    cm.__enter__.return_value = _response(payload)
                    cm.__exit__.return_value = False
                    return cm
            raise AssertionError(f"unexpected url {url}")

        return fake

    async def test_average_of_venues(self):
        mapping = {
            "coinbase": {"data": {"amount": "100"}},
            "kraken": {"result": {"XXBTZUSD": {"c": ["110", "1"]}}},
            "bitstamp": {"last": "120"},
            "gemini": {"last": "130"},
        }
        with mock.patch("urllib.request.urlopen", side_effect=self._urlopen_for(mapping)):
            price = await self.source.price_usd()
        self.assertEqual(price, 115.0)

    async def test_skips_failed_venue(self):
        mapping = {
            "coinbase": {"data": {"amount": "100"}},
            "kraken": {"result": {"XXBTZUSD": {"c": ["200", "1"]}}},
            "bitstamp": {"last": "300"},
            "gemini": {"last": "400"},
        }
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=self._urlopen_for(mapping, fail={"gemini"}),
        ):
            with self.assertLogs("blockclock_backend.pricing", level="WARNING") as logs:
                price = await self.source.price_usd()
        self.assertEqual(price, 200.0)
        self.assertTrue(any("gemini" in line for line in logs.output))

    async def test_failed_venue_not_logged_twice(self):
        mapping = {
            "coinbase": {"data": {"amount": "100"}},
            "kraken": {"result": {"XXBTZUSD": {"c": ["100", "1"]}}},
            "bitstamp": {"last": "100"},
            "gemini": {"last": "100"},
        }
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=self._urlopen_for(mapping, fail={"bitstamp"}),
        ):
            with self.assertLogs("blockclock_backend.pricing", level="WARNING") as first:
                await self.source.price_usd()
            self.source._loaded_at = 0.0
            await self.source.price_usd()
        self.assertEqual(sum(1 for line in first.output if "bitstamp" in line), 1)
        # Still marked down after second refresh with no extra warning path exercised.
        self.assertIn("bitstamp", self.source._down)

    async def test_coinbase_spot_separate(self):
        mapping = {
            "coinbase": {"data": {"amount": "50"}},
            "kraken": {"result": {"XXBTZUSD": {"c": ["150", "1"]}}},
            "bitstamp": {"last": "150"},
            "gemini": {"last": "150"},
        }
        with mock.patch("urllib.request.urlopen", side_effect=self._urlopen_for(mapping)):
            self.assertEqual(await self.source.coinbase_spot_usd(), 50.0)
            self.assertEqual(await self.source.price_usd(), 125.0)

    async def test_cache_avoids_refetch(self):
        mapping = {
            "coinbase": {"data": {"amount": "100"}},
            "kraken": {"result": {"XXBTZUSD": {"c": ["100", "1"]}}},
            "bitstamp": {"last": "100"},
            "gemini": {"last": "100"},
        }
        fake = mock.Mock(side_effect=self._urlopen_for(mapping))
        with mock.patch("urllib.request.urlopen", fake):
            await self.source.price_usd()
            await self.source.price_usd()
        self.assertEqual(fake.call_count, 4)

    async def test_static_price_wins(self):
        source = ConfiguredPriceSource(64520.0, "", "", 1, 30, self.venues)
        self.assertEqual(await source.price_usd(), 64520.0)
        self.assertEqual(await source.coinbase_spot_usd(), 64520.0)

    async def test_no_venues_errors(self):
        source = ConfiguredPriceSource(None, "", "", 1, 30, ())
        with self.assertRaises(DataSourceError):
            await source.price_usd()
