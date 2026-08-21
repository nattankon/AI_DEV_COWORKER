import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class _FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class CustomAnthropicProviderTests(unittest.TestCase):
    def test_profile_persists_endpoint_and_models_without_key(self):
        from custom_anthropic_provider import load_profile, save_profile

        with tempfile.TemporaryDirectory() as root:
            saved = save_profile(root, "https://proxy.example.com", ["claude-sonnet-custom"])
            loaded = load_profile(root)

            self.assertEqual(saved["base_url"], "https://proxy.example.com/v1")
            self.assertEqual(loaded["models"], ["claude-sonnet-custom"])
            raw = (Path(root) / "custom_anthropic_provider.json").read_text(encoding="utf-8")
            self.assertNotIn("api_key", raw)
            self.assertNotIn("secret", raw)

    def test_rejects_non_http_endpoint(self):
        from custom_anthropic_provider import save_profile

        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "HTTP"):
                save_profile(root, "file:///tmp/provider", [])

    @patch("custom_anthropic_provider.urlopen")
    def test_import_models_uses_bearer_auth_and_models_endpoint(self, urlopen):
        from custom_anthropic_provider import import_models

        urlopen.return_value = _FakeResponse({"data": [{"id": "claude-sonnet-5"}, {"id": "claude-opus-5"}]})

        models = import_models("https://proxy.example.com", "secret-key", timeout=9)

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://proxy.example.com/v1/models")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-key")
        self.assertEqual(models, ["claude-opus-5", "claude-sonnet-5"])

    def test_provider_status_exposes_imported_models_without_secret(self):
        from custom_anthropic_provider import provider_status, save_profile

        with tempfile.TemporaryDirectory() as root:
            save_profile(root, "https://proxy.example.com/v1", ["claude-sonnet-5"])
            status = provider_status(root, configured=True)

            self.assertEqual(status["id"], "anthropic_compatible")
            self.assertEqual(status["models"][0]["id"], "anthropic-compatible:claude-sonnet-5")
            self.assertEqual(status["models"][0]["context_window_tokens"], 200_000)
            self.assertNotIn("key", json.dumps(status).casefold())


if __name__ == "__main__":
    unittest.main()
