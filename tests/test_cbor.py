import math
import unittest

from blockclock_backend import cbor


class CBORTests(unittest.TestCase):
    def test_round_trip_protocol_values(self):
        values = [
            None,
            True,
            False,
            0,
            23,
            24,
            65_535,
            2**40,
            -1,
            -1000,
            64_520.5,
            b"challenge",
            "Bitcoin",
            [1, "two", False],
            {"cmd": "get_value", "arg": "electrum.BTC.block_height", "reqid": 100001},
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(cbor.loads(cbor.dumps(value)), value)

    def test_nan_round_trip(self):
        self.assertTrue(math.isnan(cbor.loads(cbor.dumps(float("nan")))))

    def test_rejects_trailing_data(self):
        with self.assertRaises(cbor.CBORError):
            cbor.loads(b"\x01\x02")

    def test_decodes_firmware_style_float32(self):
        self.assertEqual(cbor.loads(bytes.fromhex("fa477c0800")), 64520.0)

