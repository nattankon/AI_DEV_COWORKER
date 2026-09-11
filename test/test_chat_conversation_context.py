import unittest

from chat_conversation_context import plan_conversation_context, reduce_messages_for_retry, split_history_for_manual_compaction


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

    def test_soft_context_target_compacts_before_the_advertised_hard_limit(self):
        history = []
        for index in range(16):
            history.extend(
                [
                    {"role": "user", "content": f"question {index} " + ("x" * 1_000)},
                    {"role": "assistant", "content": f"answer {index} " + ("y" * 1_000)},
                ]
            )

        plan = plan_conversation_context(
            history,
            model_id="local:unknown",
            context_window_tokens=10_000,
            target_utilization=0.65,
            fixed_messages=[{"role": "system", "content": "system"}],
            output_tokens=500,
        )

        self.assertEqual(plan.target_context_tokens, 6_500)
        self.assertTrue(plan.compacted_history)
        self.assertEqual(plan.recent_history[-2]["content"].split()[1], "15")
        self.assertEqual(plan.recent_history[-1]["content"].split()[1], "15")
        self.assertLessEqual(plan.fixed_tokens + plan.history_tokens + plan.summary_reserve_tokens, plan.input_budget_tokens)

    def test_retry_reduction_preserves_system_current_user_and_recent_complete_turn(self):
        messages = [
            {"role": "system", "content": "role and safety"},
            {"role": "user", "content": "old question " + ("x" * 2_000)},
            {"role": "assistant", "content": "old answer " + ("y" * 2_000)},
            {"role": "user", "content": "recent question " + ("a" * 400)},
            {"role": "assistant", "content": "recent answer " + ("b" * 400)},
            {"role": "user", "content": "current request"},
        ]

        reduced = reduce_messages_for_retry(messages, target_tokens=500)

        self.assertEqual(reduced[0], messages[0])
        self.assertEqual(reduced[-1], messages[-1])
        self.assertIn(messages[3], reduced)
        self.assertIn(messages[4], reduced)
        self.assertNotIn(messages[1], reduced)
        self.assertNotIn(messages[2], reduced)

    def test_manual_compaction_splits_old_dialogue_from_four_recent_complete_turns(self):
        history = []
        for index in range(6):
            history.extend([
                {"role": "user", "content": f"question {index}"},
                {"role": "assistant", "content": f"answer {index}"},
            ])

        compacted, recent = split_history_for_manual_compaction(history, recent_turns=4)

        self.assertEqual([item["content"] for item in compacted], [
            "question 0", "answer 0", "question 1", "answer 1",
        ])
        self.assertEqual([item["content"] for item in recent], [
            "question 2", "answer 2", "question 3", "answer 3",
            "question 4", "answer 4", "question 5", "answer 5",
        ])
