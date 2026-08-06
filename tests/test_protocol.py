import unittest

from blockclock_backend.protocol import ProtocolError, decode_frame, encode_frame


class ProtocolTests(unittest.TestCase):
    def test_known_greeting_frame(self):
        frame = bytes.fromhex(
            "bc00003da26b6d696e5f76657273696f6e83000101696368616c6c656e67655820"
            "355954334f47515a47375047504135554c533454455954465348414449485935"
        )
        self.assertEqual(
            decode_frame(frame),
            {
                "min_version": [0, 1, 1],
                "challenge": b"5YT3OGQZG7PGPA5ULS4TEYTFSHADIHY5",
            },
        )

    def test_round_trip(self):
        message = {"reqid": 7, "pong": "hello"}
        self.assertEqual(decode_frame(encode_frame(message)), message)

    def test_bad_magic(self):
        frame = bytearray(encode_frame({"ok": True}))
        frame[0] = 0
        with self.assertRaises(ProtocolError):
            decode_frame(bytes(frame))

