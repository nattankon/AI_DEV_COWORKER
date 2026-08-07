from pathlib import Path
import unittest

from secret_guard import SecretAccessError, SecretGuard


class SecretGuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = SecretGuard()

    def test_blocks_environment_secret_files_but_allows_templates(self):
        for value in [".env", ".ENV", ".env.local", "config/.env.production", ".env:backup"]:
            with self.subTest(value=value):
                with self.assertRaises(SecretAccessError):
                    self.guard.require_allowed(Path(value))

        for value in [".env.example", ".env.sample", ".env.template"]:
            with self.subTest(value=value):
                self.guard.require_allowed(Path(value))

    def test_blocks_private_keys_and_credential_stores(self):
        blocked = [
            "id_rsa",
            "id_rsa:backup",
            "keys/id_ed25519",
            "certs/server.pem",
            "certs/signing.key",
            "certs/client.p12",
            ".ssh/config",
            ".aws/credentials",
            ".azure/accessTokens.json",
            ".gnupg/private-keys-v1.d/key",
            ".kube/config",
            ".git-credentials",
        ]

        for value in blocked:
            with self.subTest(value=value):
                with self.assertRaises(SecretAccessError):
                    self.guard.require_allowed(Path(value))

    def test_explains_denial_without_exposing_file_content(self):
        decision = self.guard.evaluate(Path("secrets/private.pem"))

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "private key or certificate file")

    def test_blocks_the_app_provider_key_stores(self):
        # The app's own credential files (canonical + legacy name) must be invisible
        # to the agent's read/write tools; the app loads them directly, bypassing the guard.
        for value in ["credentials.txt", "key.txt", "sub/dir/key.txt", "KEY.TXT"]:
            with self.subTest(value=value):
                decision = self.guard.evaluate(Path(value))
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, "credential file")

    def test_still_allows_ordinary_source_files(self):
        for value in ["main.py", "notes.txt", "src/app.js", "keys.md"]:
            with self.subTest(value=value):
                self.guard.require_allowed(Path(value))


if __name__ == "__main__":
    unittest.main()
