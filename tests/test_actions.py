import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from actions import ActionDispatcher, ActionError


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def runner(argv):
            self.calls.append(argv)
            return {"stdout": "ok"}

        self.dispatcher = ActionDispatcher(runner=runner)

    def test_open_uses_argument_array(self):
        result = self.dispatcher.dispatch("ui.open", {"app": "calculator"})
        self.assertEqual(result["stdout"], "ok")
        self.assertEqual(self.calls[-1], ["open", "calculator"])

    def test_invalid_app_rejected(self):
        with self.assertRaises(ActionError):
            self.dispatcher.dispatch("ui.open", {"app": "calculator; rm -rf /"})
        self.assertEqual(self.calls, [])

    def test_percent_bounded(self):
        with self.assertRaises(ActionError):
            self.dispatcher.dispatch("device.volume", {"value": 101})
        self.assertEqual(self.calls, [])

    def test_unknown_action_rejected(self):
        with self.assertRaises(ActionError):
            self.dispatcher.dispatch("system.shell", {"cmd": "id"})
        self.assertEqual(self.calls, [])

    def test_text_is_not_shell_parsed(self):
        text = "hello; $(touch /tmp/nope)"
        self.dispatcher.dispatch("ui.type", {"text": text})
        self.assertEqual(self.calls[-1], ["type", text])


if __name__ == "__main__":
    unittest.main()
