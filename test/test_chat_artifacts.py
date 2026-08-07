import json
import tempfile
import unittest
from pathlib import Path

from chat_artifacts import ArtifactStore, ArtifactToolProvider, detect_artifacts


class ChatArtifactsTests(unittest.TestCase):
    def test_create_artifact_versions_same_title(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ArtifactStore(Path(temp_dir))
            first = store.create_artifact("html", "Demo", "<h1>One</h1>", session_id="s1")
            second = store.create_artifact("html", "Demo", "<h1>Two</h1>", session_id="s1")

            self.assertEqual(first["version"], 1)
            self.assertEqual(second["version"], 2)
            self.assertEqual(len(store.list_artifacts()), 1)
            self.assertEqual(len(store.list_artifacts()[0]["versions"]), 2)

    def test_tool_provider_returns_standard_ok_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = ArtifactToolProvider(ArtifactStore(Path(temp_dir)), session_id="s2")

            payload = json.loads(provider.dispatch("create_artifact", {"type": "markdown", "title": "Note", "content": "# Hi"}))

            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["artifact"]["title"], "Note")

    def test_detects_full_html_code_block(self):
        artifacts = detect_artifacts("Here:\n```html\n<!doctype html><html><body>Hi</body></html>\n```")

        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["type"], "html")
        self.assertIn("<html>", artifacts[0]["content"])

    def test_plain_answer_has_no_artifact(self):
        self.assertEqual(detect_artifacts("plain short answer"), [])


if __name__ == "__main__":
    unittest.main()
