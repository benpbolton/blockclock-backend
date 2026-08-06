import unittest

from blockclock_backend.bitcoin import _btc_per_kb_to_sats_vb


class BitcoinFeeTests(unittest.TestCase):
    def test_btc_per_kb_to_sats_vb(self):
        # 0.00006 BTC/kB = 6 sat/vB
        self.assertEqual(_btc_per_kb_to_sats_vb(0.00006), 6.0)
        # 0.00001 BTC/kvB = 1 sat/vB
        self.assertEqual(_btc_per_kb_to_sats_vb(0.00001), 1.0)
