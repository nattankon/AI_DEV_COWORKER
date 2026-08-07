import unittest

from chat_runtime import CHAT_SYSTEM_PROMPT, ChatRuntimeConfig


class ChatRuntimeConfigTests(unittest.TestCase):
    def test_default_efforts_include_research_budgets(self):
        config = ChatRuntimeConfig()

        self.assertEqual(config.effort_config("Low").research_max_iterations, 4)
        self.assertEqual(config.effort_config("Low").research_max_fetch, 3)
        self.assertEqual(config.effort_config("Medium").research_max_iterations, 6)
        self.assertEqual(config.effort_config("Medium").research_max_fetch, 5)
        self.assertEqual(config.effort_config("High").research_max_iterations, 12)
        self.assertEqual(config.effort_config("High").research_max_fetch, 8)

    def test_deepseek_can_use_chat_tool_research(self):
        config = ChatRuntimeConfig()

        self.assertIn("deepseek", config.tool_research_providers)

    def test_code_execution_defaults_to_pyodide_sandbox(self):
        config = ChatRuntimeConfig()

        self.assertEqual(config.code_execution_sandbox, "pyodide")

    def test_search_depth_hints_are_data_driven_and_scale_with_effort(self):
        config = ChatRuntimeConfig()

        low = config.effort_config("Low").search_depth_hint
        medium = config.effort_config("Medium").search_depth_hint
        high = config.effort_config("High").search_depth_hint

        self.assertTrue(low)
        self.assertTrue(medium)
        self.assertTrue(high)
        self.assertEqual(len({low, medium, high}), 3)

    def test_chat_system_prompt_keeps_boundaries_silent_until_needed(self):
        self.assertIn("Be a warm, capable conversational assistant", CHAT_SYSTEM_PROMPT)
        self.assertIn("only when that boundary blocks the answer", CHAT_SYSTEM_PROMPT)
        self.assertIn("avoid volunteering mode or boundary explanations", CHAT_SYSTEM_PROMPT)
        self.assertNotIn("Chat mode", CHAT_SYSTEM_PROMPT)
        self.assertNotIn("must not read workspace files", CHAT_SYSTEM_PROMPT)
        self.assertNotIn("Cowork", CHAT_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
