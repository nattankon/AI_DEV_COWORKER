import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


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
    def test_preset_registry_is_data_driven_and_secret_free(self):
        from custom_anthropic_provider import provider_presets

        presets = provider_presets()
        by_id = {item["id"]: item for item in presets}

        self.assertEqual(by_id["mwapi"]["base_url"], "https://api.mwapi.dev/v1")
        self.assertEqual(by_id["mwapi"]["protocol"], "anthropic_messages")
        self.assertEqual(by_id["mwapi"]["auth_scheme"], "x_api_key")
        self.assertEqual(by_id["mwapi"]["models_auth_scheme"], "bearer")
        self.assertEqual(by_id["openrouter"]["auth_scheme"], "bearer")
        self.assertEqual(by_id["groq"]["protocol"], "openai_chat_completions")
        self.assertIn("custom", by_id)
        self.assertNotIn("secret-key", json.dumps(presets).casefold())

    def test_profile_persists_endpoint_and_models_without_key(self):
        from custom_anthropic_provider import load_profile, save_profile

        with tempfile.TemporaryDirectory() as root:
            saved = save_profile(
                root,
                "https://proxy.example.com",
                ["claude-sonnet-custom"],
                preset_id="custom",
                protocol="openai_chat_completions",
                auth_scheme="bearer",
                models_auth_scheme="bearer",
            )
            loaded = load_profile(root)

            self.assertEqual(saved["base_url"], "https://proxy.example.com/v1")
            self.assertEqual(loaded["models"], ["claude-sonnet-custom"])
            self.assertEqual(loaded["protocol"], "openai_chat_completions")
            self.assertEqual(loaded["auth_scheme"], "bearer")
            raw = (Path(root) / "custom_anthropic_provider.json").read_text(encoding="utf-8")
            self.assertNotIn("api_key", raw)
            self.assertNotIn("secret", raw)

    def test_load_profile_migrates_legacy_anthropic_shape(self):
        from custom_anthropic_provider import PROFILE_FILENAME, load_profile

        with tempfile.TemporaryDirectory() as root:
            (Path(root) / PROFILE_FILENAME).write_text(
                json.dumps({"base_url": "https://legacy.example.com/v1", "models": ["legacy-model"]}),
                encoding="utf-8",
            )

            loaded = load_profile(root)

            self.assertEqual(loaded["preset_id"], "custom")
            self.assertEqual(loaded["protocol"], "anthropic_messages")
            self.assertEqual(loaded["auth_scheme"], "x_api_key")
            self.assertEqual(loaded["models_auth_scheme"], "bearer")

    def test_rejects_non_http_endpoint(self):
        from custom_anthropic_provider import save_profile

        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "HTTP"):
                save_profile(root, "file:///tmp/provider", [])

    @patch("custom_anthropic_provider.httpx.request")
    def test_import_models_uses_configured_auth_and_models_endpoint(self, request):
        from custom_anthropic_provider import import_models

        response = Mock()
        response.status_code = 200
        response.json.return_value = {"data": [{"id": "claude-sonnet-5"}, {"id": "claude-opus-5"}]}
        response.raise_for_status.return_value = None
        request.return_value = response

        models = import_models(
            "https://proxy.example.com",
            "secret-key",
            timeout=9,
            auth_scheme="x_api_key",
        )

        kwargs = request.call_args.kwargs
        self.assertEqual(request.call_args.args[:2], ("GET", "https://proxy.example.com/v1/models"))
        self.assertEqual(kwargs["headers"]["x-api-key"], "secret-key")
        self.assertNotIn("Authorization", kwargs["headers"])
        self.assertEqual(kwargs["timeout"], 9)
        self.assertEqual(models, ["claude-opus-5", "claude-sonnet-5"])

    def test_provider_status_exposes_imported_models_without_secret(self):
        from custom_anthropic_provider import provider_status, save_profile

        with tempfile.TemporaryDirectory() as root:
            save_profile(root, "https://proxy.example.com/v1", ["claude-sonnet-5"])
            status = provider_status(root, configured=True)

            self.assertEqual(status["id"], "anthropic_compatible")
            self.assertEqual(status["models"][0]["id"], "anthropic-compatible:claude-sonnet-5")
            self.assertEqual(status["models"][0]["context_window_tokens"], 200_000)
            self.assertTrue(any(item["id"] == "openrouter" for item in status["presets"]))
            self.assertNotIn("secret-key", json.dumps(status).casefold())


if __name__ == "__main__":
    unittest.main()
