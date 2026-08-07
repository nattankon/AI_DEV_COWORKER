import unittest

from chat_runtime import ChatRuntimeConfig
from chat_search_api import BraveSearchProvider, get_search_provider


class ChatSearchApiTests(unittest.TestCase):
    def test_brave_provider_maps_web_results_to_normalized_shape(self):
        calls = []

        def fetcher(url, *, headers, timeout):
            calls.append((url, headers, timeout))
            return {
                "web": {
                    "results": [
                        {
                            "title": "Blender Release Notes",
                            "url": "https://www.blender.org/download/releases/4-3/",
                            "description": "Official Blender 4.3 release notes.",
                        },
                        {"title": "", "url": "https://missing-title.example", "description": "skip"},
                    ]
                }
            }

        provider = BraveSearchProvider("brave-secret", timeout_seconds=7.0, fetcher=fetcher)

        results = provider.search("Blender latest version", count=12)

        self.assertEqual(
            results,
            [
                {
                    "title": "Blender Release Notes",
                    "url": "https://www.blender.org/download/releases/4-3/",
                    "snippet": "Official Blender 4.3 release notes.",
                }
            ],
        )
        self.assertIn("q=Blender+latest+version", calls[0][0])
        self.assertIn("count=10", calls[0][0])
        self.assertEqual(calls[0][1]["X-Subscription-Token"], "brave-secret")
        self.assertEqual(calls[0][2], 7.0)

    def test_search_provider_factory_requires_key(self):
        config = ChatRuntimeConfig(search_api_key="")

        self.assertIsNone(get_search_provider(config))

    def test_search_provider_factory_creates_brave_provider_when_key_exists(self):
        config = ChatRuntimeConfig(search_api_key="brave-secret", search_api_provider="brave")

        self.assertIsInstance(get_search_provider(config), BraveSearchProvider)


if __name__ == "__main__":
    unittest.main()
