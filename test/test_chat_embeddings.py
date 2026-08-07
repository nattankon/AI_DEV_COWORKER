import builtins
import unittest

import chat_embeddings


class ChatEmbeddingsTests(unittest.TestCase):
    def test_create_local_embedder_returns_none_when_fastembed_missing(self):
        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "fastembed":
                raise ImportError("fastembed missing")
            return original_import(name, *args, **kwargs)

        builtins.__import__ = fake_import
        try:
            self.assertIsNone(chat_embeddings.create_local_embedder())
        finally:
            builtins.__import__ = original_import


if __name__ == "__main__":
    unittest.main()
