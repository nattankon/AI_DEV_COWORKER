import unittest

from chat_research_strategy import build_research_plan


class ChatResearchStrategyTests(unittest.TestCase):
    def test_docs_query_prefers_official_documentation_sources_from_registry(self):
        plan = build_research_plan("OpenAI API structured outputs latest docs")

        self.assertEqual(plan.answer_language, "en")
        self.assertTrue(any("official documentation" in query for query in plan.queries))
        self.assertTrue(any("official" in hint.get("source_type", "") for hint in plan.source_preferences))

    def test_pricing_query_prefers_official_pricing_and_status_pages_from_registry(self):
        plan = build_research_plan("Gemini API pricing and quota limits")

        self.assertTrue(any("official pricing" in query for query in plan.queries))
        self.assertTrue(any("official status quota limits" in query for query in plan.queries))
        self.assertTrue(any(hint.get("source_type") == "pricing" for hint in plan.source_preferences))

    def test_github_query_prefers_repository_sources_from_registry(self):
        plan = build_research_plan("midudev autoskills github readme")

        self.assertTrue(any("site:github.com" in query for query in plan.queries))
        self.assertTrue(any(hint.get("source_type") == "repository" for hint in plan.source_preferences))

    def test_news_query_adds_reputable_recent_source_preference_from_registry(self):
        plan = build_research_plan("latest OpenAI model release news")

        self.assertTrue(any("latest news" in query for query in plan.queries))
        self.assertTrue(any(hint.get("source_type") == "news" for hint in plan.source_preferences))

    def test_fuel_query_no_longer_gets_topic_specific_fuel_expansion(self):
        plan = build_research_plan("ขอข้อมูล ราคาน้ำมันล่าสุด ของประเทศไทย")

        self.assertEqual(plan.answer_language, "th")
        self.assertIn("ราคาน้ำมันล่าสุด ประเทศไทย", plan.queries[0])
        self.assertFalse(any("fuel prices" in query.casefold() for query in plan.queries))
        self.assertFalse(any(hint.get("source_type") == "industry" for hint in plan.source_preferences))

    def test_custom_query_type_profile_is_data_driven(self):
        profiles = (
            {
                "keywords": ("benchmark",),
                "query_templates": ("{q} official benchmark methodology",),
                "source_hints": (
                    {"source_type": "benchmark", "hint": "Prefer reproducible benchmark methodology."},
                ),
            },
        )

        plan = build_research_plan("model benchmark results", profiles=profiles)

        self.assertEqual(
            plan.queries,
            ("model benchmark results", "model benchmark results official benchmark methodology"),
        )
        self.assertEqual(plan.source_preferences[0]["source_type"], "benchmark")


if __name__ == "__main__":
    unittest.main()
