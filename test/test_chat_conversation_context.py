import unittest

from chat_conversation_context import plan_conversation_context


class ChatConversationContextTests(unittest.TestCase):
    def test_uses_selected_catalog_window_instead_of_effort_message_count(self):
        history = [
            {"role": "user", "content": f"question {index}"}
            for index in range(12)
        ]
        plan = plan_conversation_context(
            history,
            model_id="zai:glm-4.5-flash",
            fixed_messages=[{"role": "system", "content": "system"}],
            output_tokens=1024,
        )

        self.assertEqual(plan.context_window_tokens, 131_072)
        self.assertEqual(plan.recent_history, history)
        self.assertEqual(plan.compacted_history, [])

    def test_compacts_old_turns_but_keeps_recent_turns_inside_small_window(self):
        history = []
        for index in range(8):
            history.extend(
                [
                    {"role": "user", "content": f"question {index} " + ("x" * 900)},
                    {"role": "assistant", "content": f"answer {index} " + ("y" * 900)},
                ]
            )

        plan = plan_conversation_context(
            history,
            model_id="local:unknown",
            context_window_tokens=2_000,
            fixed_messages=[{"role": "system", "content": "system"}],
            output_tokens=256,
        )

        self.assertTrue(plan.compacted_history)
        self.assertLess(len(plan.recent_history), len(history))
        self.assertEqual(plan.recent_history[-2]["content"].split()[1], "7")
        self.assertEqual(plan.recent_history[-1]["content"].split()[1], "7")
        self.assertLessEqual(plan.history_tokens + plan.summary_reserve_tokens, plan.history_budget_tokens)

    def test_context_budget_accounts_for_current_prompt_and_output_reservation(self):
        plan = plan_conversation_context(
            [{"role": "user", "content": "old context"}],
            model_id="local:unknown",
            context_window_tokens=4_000,
            fixed_messages=[
                {"role": "system", "content": "system " * 100},
                {"role": "user", "content": "current " * 100},
            ],
            output_tokens=1_000,
        )

        self.assertEqual(plan.input_budget_tokens, 2_840)
        self.assertGreater(plan.fixed_tokens, 0)
        self.assertEqual(plan.history_budget_tokens, plan.input_budget_tokens - plan.fixed_tokens)

    def test_oversized_latest_turn_is_compacted_instead_of_overflowing_window(self):
        history = [
            {"role": "user", "content": "x" * 20_000},
            {"role": "assistant", "content": "y" * 20_000},
        ]

        plan = plan_conversation_context(
            history,
            model_id="local:unknown",
            context_window_tokens=2_000,
            fixed_messages=[{"role": "system", "content": "system"}],
            output_tokens=256,
        )

        self.assertEqual(plan.recent_history, [])
        self.assertEqual(plan.compacted_history, history)
        self.assertLessEqual(plan.history_tokens + plan.summary_reserve_tokens, plan.history_budget_tokens)
