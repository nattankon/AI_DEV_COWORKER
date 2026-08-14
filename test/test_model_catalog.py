import tempfile
import unittest
from pathlib import Path

from model_catalog import catalog_model_metadata, catalog_model_supports_vision, detect_provider_keys, read_provider_api_key, save_provider_key


class SaveProviderKeyTests(unittest.TestCase):
    def test_catalog_includes_paid_zai_vision_helpers(self):
        flashx = catalog_model_metadata("zai:glm-4.6v-flashx")
        full = catalog_model_metadata("zai:glm-4.6v")

        self.assertEqual(flashx["billing"], "paid")
        self.assertTrue(catalog_model_supports_vision("zai:glm-4.6v-flashx"))
        self.assertGreater(flashx["context_window_tokens"], 0)
        self.assertEqual(full["billing"], "paid")
        self.assertTrue(catalog_model_supports_vision("zai:glm-4.6v"))
        self.assertGreater(full["context_window_tokens"], 0)

    def test_catalog_includes_the_free_zai_vision_model(self):
        model = catalog_model_metadata("zai:glm-4.6v-flash")

        self.assertEqual(model["label"], "GLM-4.6V-Flash")
        self.assertEqual(model["billing"], "free")
        self.assertTrue(catalog_model_supports_vision("zai:glm-4.6v-flash"))

    def test_saves_and_classifies_each_provider_back_correctly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertTrue(save_provider_key(root, "zai", "zaikeyAAA"))
            self.assertTrue(save_provider_key(root, "openai", "sk-proj-BBB"))
            self.assertTrue(save_provider_key(root, "Gemini", "AIzaCCC"))  # case-insensitive

            self.assertEqual(sorted(k.provider_id for k in detect_provider_keys(root)), ["gemini", "openai", "zai"])
            self.assertEqual(read_provider_api_key(root, "zai"), "zaikeyAAA")
            self.assertEqual(read_provider_api_key(root, "gemini"), "AIzaCCC")

    def test_replaces_existing_key_for_the_same_provider(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            save_provider_key(root, "zai", "zaiOLD")
            save_provider_key(root, "zai", "zaiNEW")

            zai_keys = [k for k in detect_provider_keys(root) if k.provider_id == "zai"]
            self.assertEqual(len(zai_keys), 1)  # no duplicate line
            self.assertEqual(read_provider_api_key(root, "zai"), "zaiNEW")

    def test_writes_to_credentials_txt_canonical_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            save_provider_key(root, "openai", "sk-proj-XYZ")
            self.assertTrue((root / "credentials.txt").is_file())

    def test_rejects_unknown_provider_empty_or_multiline_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertFalse(save_provider_key(root, "notaprovider", "x"))
            self.assertFalse(save_provider_key(root, "zai", ""))
            self.assertFalse(save_provider_key(root, "zai", "line1\nline2"))
            self.assertEqual(detect_provider_keys(root), [])


if __name__ == "__main__":
    unittest.main()
