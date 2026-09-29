import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mqtt_client import MQTTClient, _pack_str, _remaining_length


class MQTTEncodingTests(unittest.TestCase):
    def test_pack_string(self):
        self.assertEqual(_pack_str("sol/v1/cmd"), b"\x00\x0asol/v1/cmd")

    def test_remaining_length_examples(self):
        self.assertEqual(_remaining_length(0), b"\x00")
        self.assertEqual(_remaining_length(127), b"\x7f")
        self.assertEqual(_remaining_length(128), b"\x80\x01")
        self.assertEqual(_remaining_length(16384), b"\x80\x80\x01")

    def test_decode_qos0_publish_body(self):
        body = _pack_str("sol/v1/cmd") + b'{"v":1}'
        topic, payload = MQTTClient.decode_publish(body)
        self.assertEqual(topic, "sol/v1/cmd")
        self.assertEqual(payload, b'{"v":1}')


if __name__ == "__main__":
    unittest.main()
