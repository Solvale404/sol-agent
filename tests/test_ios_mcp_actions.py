import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from actions import ActionDispatcher, ActionError


class FakeMCP:
    def __init__(self):
        self.calls = []

    def health(self):
        return {"status": "ok", "version": "test"}

    def call_tool(self, name, args):
        self.calls.append((name, args))
        if name == "get_screen_info":
            return {"locked": False, "screen_on": True}
        if name == "get_frontmost_app":
            return {"bundleId": "com.apple.springboard"}
        return {"ok": True}


class IOSMCPActionTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        self.dispatcher = ActionDispatcher(driver="ios_mcp", mcp_client=self.mcp)

    def test_calculator_alias_maps_to_bundle(self):
        self.dispatcher.dispatch("ui.open", {"app": "calculator"})
        self.assertEqual(self.mcp.calls[-1], ("launch_app", {"bundle_id": "com.apple.calculator"}))

    def test_bundle_id_passes_through(self):
        self.dispatcher.dispatch("ui.open", {"app": "com.example.app"})
        self.assertEqual(self.mcp.calls[-1], ("launch_app", {"bundle_id": "com.example.app"}))

    def test_unknown_alias_rejected(self):
        with self.assertRaises(ActionError):
            self.dispatcher.dispatch("ui.open", {"app": "not-a-real-alias"})

    def test_percent_is_normalized(self):
        self.dispatcher.dispatch("device.volume", {"value": 30})
        self.assertEqual(self.mcp.calls[-1], ("set_volume", {"level": 0.3}))

    def test_unimplemented_remotecompanion_actions_not_advertised(self):
        names = {item["action"] for item in self.dispatcher.manifest()}
        self.assertNotIn("device.wifi", names)
        self.assertNotIn("notify.toast", names)
        with self.assertRaises(ActionError):
            self.dispatcher.dispatch("device.wifi", {"state": "off"})

    def test_available_uses_local_health(self):
        self.assertTrue(self.dispatcher.available())


if __name__ == "__main__":
    unittest.main()
