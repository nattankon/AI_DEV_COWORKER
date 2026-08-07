import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cli_config import parse_cli_args


class CliConfigTests(unittest.TestCase):
    def test_defaults_to_lm_studio_and_current_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {}, clear=True):
                config = parse_cli_args(["--prompt", "inspect this repo"], cwd=Path(temp_dir))

        self.assertEqual(config.base_url, "http://127.0.0.1:1234/v1")
        self.assertEqual(config.workspace, Path(temp_dir).resolve())
        self.assertEqual(config.model, "local:qwen/qwen3.5-9b")
        self.assertEqual(config.model_id, "qwen/qwen3.5-9b")
        self.assertEqual(config.prompt, "inspect this repo")
        self.assertFalse(config.auto_approve)

    def test_environment_supplies_local_ai_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env = {
                "LOCAL_AI_BASE_URL": "http://127.0.0.1:9999/v1/",
                "LOCAL_AI_API_KEY": "secret-value",
                "LOCAL_AI_MODEL": "local:test/model",
            }
            with patch.dict(os.environ, env, clear=True):
                config = parse_cli_args([], cwd=Path(temp_dir))

        self.assertEqual(config.base_url, "http://127.0.0.1:9999/v1")
        self.assertEqual(config.api_key, "secret-value")
        self.assertEqual(config.model_id, "test/model")

    def test_rejects_missing_workspace(self):
        missing = Path(tempfile.gettempdir()) / "cowork-workspace-that-does-not-exist"
        with self.assertRaisesRegex(ValueError, "Workspace directory does not exist"):
            parse_cli_args(["--workspace", str(missing)])

    def test_parses_noninteractive_flags(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = parse_cli_args(
                [
                    "--workspace",
                    temp_dir,
                    "--yes",
                    "--list-models",
                    "--max-iterations",
                    "7",
                ]
            )

        self.assertTrue(config.auto_approve)
        self.assertTrue(config.list_models)
        self.assertEqual(config.max_iterations, 7)


if __name__ == "__main__":
    unittest.main()
