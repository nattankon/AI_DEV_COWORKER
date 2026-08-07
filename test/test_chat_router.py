import unittest

from chat_router import ChatRoute, classify_chat_prompt


class ChatRouterTests(unittest.TestCase):
    def test_general_question_does_not_request_project_context(self):
        route = classify_chat_prompt("อธิบายว่า recursion คืออะไร")

        self.assertEqual(route.category, "general")
        self.assertFalse(route.needs_project_context)
        self.assertFalse(route.needs_web_context)

    def test_memory_question_routes_to_memory(self):
        route = classify_chat_prompt("จำสไตล์การตอบของผมได้ไหม")

        self.assertEqual(route.category, "memory")
        self.assertTrue(route.needs_personal_memory)

    def test_project_question_routes_to_project_context(self):
        route = classify_chat_prompt("โปรเจกต์นี้ตอนนี้ทำถึงไหนแล้ว")

        self.assertEqual(route.category, "project")
        self.assertTrue(route.needs_project_context)

    def test_project_route_prompt_keeps_chat_out_of_workspace(self):
        route = ChatRoute(category="project", reasons=("mentions project/workspace context",), needs_project_context=True)

        block = route.to_prompt_block()

        self.assertIn("Chat Route: project", block)
        self.assertIn("project-specific evidence", block)
        self.assertIn("workspace handoff", block)
        self.assertIn("only when that evidence is required", block)
        self.assertNotIn("Chat cannot read workspace files automatically", block)

    def test_current_external_question_routes_to_web(self):
        route = classify_chat_prompt("ข่าวล่าสุดของ Gemini API วันนี้คืออะไร")

        self.assertEqual(route.category, "web")
        self.assertTrue(route.needs_web_context)

    def test_project_question_with_latest_fact_routes_to_mixed(self):
        route = classify_chat_prompt("โปรเจกต์นี้ควรใช้ Gemini รุ่นล่าสุดตัวไหน")

        self.assertEqual(route.category, "mixed")
        self.assertTrue(route.needs_project_context)
        self.assertTrue(route.needs_web_context)

    def test_route_prompt_block_labels_missing_connectors(self):
        route = ChatRoute(category="web", reasons=("asks for current facts",), needs_web_context=True)

        block = route.to_prompt_block()

        self.assertIn("Chat Route: web", block)
        self.assertIn("No web connector is available yet", block)

    def test_route_prompt_adds_answer_grounding_contract(self):
        route = ChatRoute(category="general", reasons=("ordinary knowledge question",))

        block = route.to_prompt_block()

        self.assertIn("Separate facts, assumptions, and suggestions", block)
        self.assertIn("say what is missing", block)

    def test_web_route_blocks_current_fact_guessing_without_connector(self):
        route = ChatRoute(category="web", reasons=("asks for current facts",), needs_web_context=True)

        block = route.to_prompt_block()

        self.assertIn("Do not answer current or external facts from stale model memory", block)
        self.assertIn("live/source lookup is not available", block)

    def test_web_route_with_context_requires_search_before_stating_facts(self):
        route = ChatRoute(category="web", reasons=("asks for current facts",), needs_web_context=True)

        block = route.to_prompt_block(has_web_context=True)

        self.assertIn(
            "Before stating any current or external fact, call web_search, then web_fetch the most relevant results",
            block,
        )
        self.assertIn("[web:N] citation", block)
        self.assertIn("say so instead of answering from memory", block)

    def test_mixed_route_with_context_requires_search_before_stating_facts(self):
        route = ChatRoute(
            category="mixed",
            reasons=("mentions project/workspace context", "asks for current or external facts"),
            needs_project_context=True,
            needs_web_context=True,
        )

        block = route.to_prompt_block(has_web_context=True)

        self.assertIn("Before stating any current or external fact, call web_search", block)

    def test_general_and_memory_blocks_do_not_require_search_before_stating_facts(self):
        general_block = ChatRoute(category="general", reasons=("ordinary knowledge question",)).to_prompt_block()
        memory_block = ChatRoute(category="memory", reasons=("asks about remembered user preferences",)).to_prompt_block()

        self.assertNotIn("Before stating any current or external fact", general_block)
        self.assertNotIn("Before stating any current or external fact", memory_block)

    def test_search_depth_hint_is_data_driven_and_differs_by_effort(self):
        route = ChatRoute(category="web", reasons=(), needs_web_context=True)

        low_block = route.to_prompt_block(has_web_context=True, search_depth_hint="open at least the single best source")
        high_block = route.to_prompt_block(
            has_web_context=True,
            search_depth_hint="search more than once if the first results are weak, and open several sources",
        )

        self.assertIn("open at least the single best source", low_block)
        self.assertNotIn("search more than once", low_block)
        self.assertIn("search more than once if the first results are weak, and open several sources", high_block)
        self.assertNotEqual(low_block, high_block)

    def test_search_depth_hint_is_omitted_without_web_context(self):
        route = ChatRoute(category="web", reasons=(), needs_web_context=True)

        block = route.to_prompt_block(has_web_context=False, search_depth_hint="open at least the single best source")

        self.assertNotIn("open at least the single best source", block)

    def test_mcp_connector_questions_route_to_the_mcp_category(self):
        from chat_router import classify_chat_prompt

        thai = classify_chat_prompt("ทดสอบการเชื่อมต่อ MCP Roblox")
        english = classify_chat_prompt("Is my calendar connector available?")
        plain = classify_chat_prompt("Explain what a closure is.")
        hardware = classify_chat_prompt("Which connector does HDMI 2.1 use?")

        # MCP questions must land in a loop-entering category (the default
        # tool_research_routes tuple includes "mcp") or diagnostics tools are dead.
        self.assertEqual(thai.category, "mcp")
        self.assertEqual(english.category, "mcp")
        self.assertEqual(plain.category, "general")
        # Bare "connector" without app context must NOT enter the tool loop —
        # a false positive costs real web-search latency.
        self.assertEqual(hardware.category, "general")


if __name__ == "__main__":
    unittest.main()
