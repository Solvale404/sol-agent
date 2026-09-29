import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from protocol import ProtocolError, validate_command


class ProtocolTests(unittest.TestCase):
    def base(self):
        return {
            "v": 1,
            "id": "test-1",
            "action": "system.ping",
            "args": {},
            "sent_at": 1000.0,
            "ttl": 30,
            "source": "test",
        }

    def test_valid(self):
        cmd, expired = validate_command(self.base(), now=1010.0)
        self.assertEqual(cmd["action"], "system.ping")
        self.assertFalse(expired)

    def test_expired(self):
        _, expired = validate_command(self.base(), now=1031.0)
        self.assertTrue(expired)

    def test_args_must_be_object(self):
        raw = self.base()
        raw["args"] = "nope"
        with self.assertRaises(ProtocolError):
            validate_command(raw, now=1001.0)

    def test_ttl_is_bounded(self):
        raw = self.base()
        raw["ttl"] = 9999
        with self.assertRaises(ProtocolError):
            validate_command(raw, now=1001.0)

    def test_invalid_id_rejected(self):
        raw = self.base()
        raw["id"] = "contains spaces"
        with self.assertRaises(ProtocolError):
            validate_command(raw, now=1001.0)


if __name__ == "__main__":
    unittest.main()
