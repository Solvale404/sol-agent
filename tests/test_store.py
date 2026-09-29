import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent import CommandStore


class CommandStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CommandStore(os.path.join(self.tmp.name, "commands.db"))

    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()

    def test_put_replaces_same_id(self):
        self.store.put({"id": "same", "action": "system.ping", "status": "accepted"})
        self.store.put({"id": "same", "action": "system.ping", "status": "ok", "result": {"pong": True}})
        row = self.store.get("same")
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["result"], {"pong": True})
        count = self.store.db.execute("SELECT COUNT(*) FROM commands WHERE id='same'").fetchone()[0]
        self.assertEqual(count, 1)

    def test_recover_inflight_does_not_replay(self):
        self.store.put({"id": "running", "action": "ui.home", "status": "running"})
        recovered = self.store.recover_inflight()
        row = self.store.get("running")
        self.assertEqual(recovered, 1)
        self.assertEqual(row["status"], "error")
        self.assertEqual(row["error"], "agent_restarted_before_completion")


if __name__ == "__main__":
    unittest.main()
