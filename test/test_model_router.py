import unittest

from model_router import route_model


MODELS = [
    {"id": "openai:gpt-4o-mini", "strengths": ["vision", "chat"], "context_window_tokens": 128000},
    {"id": "deepseek:deepseek-v4-pro", "strengths": ["coding", "reasoning"], "context_window_tokens": 1000000},
    {"id": "gemini:gemini-3.5-flash", "strengths": ["research", "long-context"], "context_window_tokens": 1000000},
    {"id": "zai:glm-5.1", "strengths": ["translation", "writing"], "context_window_tokens": 200000},
    {"id": "zai:glm-4.5-flash", "strengths": ["chat"], "context_window_tokens": 131072, "default_model": True},
]


class ModelRouterTests(unittest.TestCase):
    def test_explicit_model_wins(self):
        result = route_model("write code", [], MODELS, requested_model="deepseek:deepseek-v4-pro")
        self.assertEqual(result.model_id, "deepseek:deepseek-v4-pro")
        self.assertEqual(result.reason, "explicit")

    def test_image_attachment_routes_to_vision_model_in_auto(self):
        result = route_model("what is in this image", [{"kind": "image"}], MODELS, requested_model="auto")
        self.assertEqual(result.model_id, "openai:gpt-4o-mini")
        self.assertIn("vision", result.reason)

    def test_code_prompt_routes_to_code_strong_model(self):
        result = route_model("write a lua script architecture example", [], MODELS, requested_model="auto")
        self.assertEqual(result.model_id, "deepseek:deepseek-v4-pro")
        self.assertIn("coding", result.reason)

    def test_react_app_explanation_routes_to_code_model(self):
        result = route_model("ช่วยอธิบายโครงสร้าง React app", [], MODELS, requested_model="auto")
        self.assertEqual(result.model_id, "deepseek:deepseek-v4-pro")
        self.assertIn("coding", result.reason)

    def test_auto_router_can_select_paid_top_model_when_it_is_best_fit(self):
        models = [
            {
                "id": "openai:gpt-5.5",
                "strengths": ["reasoning", "coding", "planning"],
                "context_window_tokens": 1_050_000,
                "billing": "paid",
                "recommended": True,
            },
            {
                "id": "deepseek:deepseek-v4-pro",
                "strengths": ["coding", "reasoning"],
                "context_window_tokens": 1_000_000,
                "billing": "paid-low-cost",
            },
            {
                "id": "zai:glm-4.5-flash",
                "strengths": ["chat", "coding"],
                "context_window_tokens": 131072,
                "billing": "free",
                "default_model": True,
            },
        ]

        result = route_model("ช่วยอธิบายโครงสร้าง React app", [], models, requested_model="auto")

        self.assertEqual(result.model_id, "openai:gpt-5.5")
        self.assertIn("coding", result.reason)

    def test_default_model_used_for_general_prompt(self):
        result = route_model("hello", [], MODELS, requested_model="auto")
        self.assertEqual(result.model_id, "zai:glm-4.5-flash")

    def test_research_prompt_routes_to_research_model(self):
        result = route_model("research current API docs and compare sources", [], MODELS, requested_model="auto")
        self.assertEqual(result.model_id, "gemini:gemini-3.5-flash")
        self.assertIn("research", result.reason)

    def test_translation_prompt_routes_to_translation_model(self):
        result = route_model("translate this Thai paragraph into natural English", [], MODELS, requested_model="auto")
        self.assertEqual(result.model_id, "zai:glm-5.1")
        self.assertIn("translation", result.reason)

    def test_auto_router_prefers_high_scoring_profile_for_detected_category(self):
        profile = {
            "models": {
                "deepseek:deepseek-v4-pro": {"categories": {"coding": {"executed": 3, "router_score": 0.4}}},
                "zai:glm-4.5-flash": {"categories": {"coding": {"executed": 3, "router_score": 0.95}}},
            }
        }

        result = route_model(
            "write a lua module and explain it",
            [],
            MODELS,
            requested_model="auto",
            performance_profile=profile,
        )

        self.assertEqual(result.model_id, "zai:glm-4.5-flash")
        self.assertIn("quality profile", result.reason)


if __name__ == "__main__":
    unittest.main()
