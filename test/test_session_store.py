import importlib
import os
import tempfile
import unittest
from pathlib import Path


class SessionStorePruneTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("COWORK_USER_DATA_DIR")
        os.environ["COWORK_USER_DATA_DIR"] = self.temp_dir.name
        import session_store
        # Re-import so the module picks up the temp COWORK_USER_DATA_DIR for its roots.
        self.session_store = importlib.reload(session_store)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("COWORK_USER_DATA_DIR", None)
        else:
            os.environ["COWORK_USER_DATA_DIR"] = self._prev
        import session_store
        importlib.reload(session_store)
        self.temp_dir.cleanup()

    def test_prune_keeps_only_the_most_recent_session_logs(self):
        root = self.session_store._SESSION_ROOT
        root.mkdir(parents=True, exist_ok=True)
        # Create more session files than the cap, with increasing mtimes.
        created = []
        for index in range(self.session_store._MAX_SESSION_FILES + 25):
            path = root / f"sess-{index:04d}.jsonl"
            path.write_text("{}\n", encoding="utf-8")
            os.utime(path, (index, index))  # oldest first
            created.append(path)

        self.session_store._prune_old_sessions()

        remaining = sorted(p.name for p in root.glob("*.jsonl"))
        self.assertEqual(len(remaining), self.session_store._MAX_SESSION_FILES)
        # The oldest files were removed; the newest survived.
        self.assertNotIn("sess-0000.jsonl", remaining)
        self.assertIn(f"sess-{self.session_store._MAX_SESSION_FILES + 24:04d}.jsonl", remaining)


if __name__ == "__main__":
    unittest.main()
