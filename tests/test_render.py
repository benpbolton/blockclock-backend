import unittest

from blockclock_backend.render import error, numeric, text


class RenderTests(unittest.TestCase):
    def test_block_height_matches_mini_shape(self):
        value = numeric("electrum.BTC.block_height", "Electrum Block Height", 961185)
        self.assertEqual(value.contents, [" ", "9", "6", "1", "1", "8", "5"])
        self.assertEqual(value.number, 961185.0)

    def test_price_matches_mini_shape(self):
        value = numeric(
            "cm.markets.price",
            "Market price of Bitcoin",
            64520,
            pair=("BTC", "USD"),
            symbol="$",
            decimals=0,
        )
        self.assertEqual(value.contents, ["/BTC/USD", "$", "6", "4", "5", "2", "0"])
        self.assertEqual(value.pair, ["BTC", "USD"])

    def test_text_is_seven_cells(self):
        self.assertEqual(text("clock", "Clock", "9:42").contents, list("   9:42"))

    def test_error_shape(self):
        value = error("missing", "Missing", "not configured")
        self.assertTrue(value.is_error)
        self.assertEqual(len(value.contents), 7)

