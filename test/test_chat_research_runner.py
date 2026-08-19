import json
import time
import unittest

from chat_research_runner import ChatResearchRunner
from chat_runtime import ChatEffortConfig
from chat_web_connector import WebSearchResponse, WebSearchResult


class FakeToolModel:
    def __init__(self, responses=None, *, error: Exception | None = None):
        self.responses = list(responses or [])
        self.error = error
        self.requests = []

    def complete(self, messages, tools, generation=None):
        self.requests.append({"messages": list(messages), "tools": list(tools), "generation": generation})
        if self.error:
            raise self.error
        return self.responses.pop(0)


class FakeConnector:
    def __init__(self):
        self._timeout_seconds = 1.0
        self.pages = {}
        self.searches = []
        self.fetches = []

    def search(self, query, max_results):
        self.searches.append((query, max_results))
        return WebSearchResponse(
            query=query,
            results=[WebSearchResult(title="Alpha", url="https://example.test/a", snippet="A snippet")],
        )

    def _fetcher(self, url, timeout):
        del timeout
        self.fetches.append(url)
        return self.pages[url]


class SlowConnector(FakeConnector):
    def _fetcher(self, url, timeout):
        delays = {
            "https://example.test/a": 0.3,
            "https://example.test/b": 0.2,
            "https://example.test/c": 0.1,
        }
        time.sleep(delays.get(url, 0.2))
        return super()._fetcher(url, timeout)


class ChatResearchRunnerTests(unittest.TestCase):
    def test_tool_driving_model_returns_used_tools_answer_and_sources(self):
        connector = FakeConnector()
        model = FakeToolModel(
            [
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call-1", "name": "web_search", "arguments": '{"query":"latest docs","max_results":1}'}
                    ],
                },
                {"content": "Grounded answer [web:1]", "tool_calls": []},
            ]
        )
        runner = ChatResearchRunner(
            model_factory=lambda model_name: model,
            model_candidates=lambda requested: [requested],
            web_tools_factory=lambda query: __import__("chat_web_tools").WebResearchTools(connector, relevance_query=query),
        )

        result = runner.run(
            prompt="latest docs",
            requested_model="zai:glm-4.5-flash",
            history=[],
            system_prompt="Chat system",
            generation={"temperature": 0.4, "max_tokens": 777},
        )

        self.assertTrue(result.outcome.used_tools)
        self.assertEqual(result.outcome.answer, "Grounded answer [web:1]")
        self.assertEqual(result.used_model, "zai:glm-4.5-flash")
        self.assertEqual(result.sources, [{"index": 1, "url": "https://example.test/a", "title": "Alpha", "source_type": "search-result"}])
        self.assertEqual(model.requests[0]["generation"], {"temperature": 0.4, "max_tokens": 777})
        self.assertEqual(connector.searches, [("latest docs", 1)])
        self.assertIn("web_search", json.dumps(model.requests[0]["tools"]))

    def test_no_tool_calls_reports_used_tools_false_for_step_six_fallback(self):
        model = FakeToolModel([{"content": "plain model answer", "tool_calls": []}])
        runner = ChatResearchRunner(
            model_factory=lambda _model_name: model,
            model_candidates=lambda requested: [requested],
            web_tools_factory=lambda query: __import__("chat_web_tools").WebResearchTools(FakeConnector(), relevance_query=query),
        )

        result = runner.run(
            prompt="hello",
            requested_model="zai:glm-4.5-flash",
            history=[],
            system_prompt="Chat system",
            generation=ChatEffortConfig(temperature=0.1, max_tokens=128, history_messages=2).generation_settings(),
        )

        self.assertFalse(result.outcome.used_tools)
        self.assertEqual(result.outcome.answer, "plain model answer")
        self.assertEqual(result.sources, [])

    def test_research_instruction_tells_model_to_use_relevant_mcp_read_tools(self):
        model = FakeToolModel([{"content": "plain model answer", "tool_calls": []}])
        runner = ChatResearchRunner(
            model_factory=lambda _model_name: model,
            model_candidates=lambda requested: [requested],
            web_tools_factory=lambda query: __import__("chat_web_tools").WebResearchTools(FakeConnector(), relevance_query=query),
        )

        runner.run(
            prompt="how many parts are in Roblox Studio?",
            requested_model="zai:glm-4.5-flash",
            history=[],
            system_prompt="Chat system",
            generation={"max_tokens": 300},
        )

        system_text = "\n".join(str(message.get("content") or "") for message in model.requests[0]["messages"] if message.get("role") == "system")
        self.assertIn("MCP", system_text)
        self.assertIn("read-only", system_text)
        self.assertIn("Do not stop at listing MCP tools", system_text)

    def test_first_model_error_falls_back_to_next_candidate(self):
        calls = []
        models = {
            "local:primary": FakeToolModel(error=RuntimeError("Request timed out.")),
            "local:fallback": FakeToolModel([{"content": "fallback answer", "tool_calls": []}]),
        }

        def model_factory(model_name):
            calls.append(model_name)
            return models[model_name]

        runner = ChatResearchRunner(
            model_factory=model_factory,
            model_candidates=lambda _requested: ["local:primary", "local:fallback"],
            web_tools_factory=lambda query: __import__("chat_web_tools").WebResearchTools(FakeConnector(), relevance_query=query),
        )

        result = runner.run(
            prompt="hello",
            requested_model="local:primary",
            history=[],
            system_prompt="Chat system",
            generation={"temperature": 0.2},
        )

        self.assertEqual(calls, ["local:primary", "local:fallback"])
        self.assertEqual(result.used_model, "local:fallback")
        self.assertEqual(result.outcome.answer, "fallback answer")

    def test_web_fetch_uses_user_query_for_relevance(self):
        connector = FakeConnector()
        connector.pages["https://example.test/page"] = """
        <html><head><title>Generic Site</title></head><body>
          <p>Unrelated introduction repeated enough to crowd the evidence budget.</p>
          <p>Needle fact appears in this paragraph for the user's question.</p>
        </body></html>
        """
        model = FakeToolModel(
            [
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call-1", "name": "web_fetch", "arguments": '{"url":"https://example.test/page"}'}
                    ],
                },
                {"content": "Needle answer [web:1]", "tool_calls": []},
            ]
        )
        runner = ChatResearchRunner(
            model_factory=lambda _model_name: model,
            model_candidates=lambda requested: [requested],
            web_tools_factory=lambda query: __import__("chat_web_tools").WebResearchTools(connector, relevance_query=query),
        )

        runner.run(
            prompt="needle",
            requested_model="zai:glm-4.5-flash",
            history=[],
            system_prompt="Chat system",
            generation={"max_tokens": 300},
        )

        tool_message = model.requests[1]["messages"][-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertIn("Needle fact", tool_message["content"])

    def test_forwards_tool_loop_events_to_status_callback(self):
        connector = FakeConnector()
        connector.pages["https://example.test/page"] = """
        <html><head><title>Evidence</title></head><body>
          <p>Fetched evidence.</p>
        </body></html>
        """
        events = []
        model = FakeToolModel(
            [
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call-1", "name": "web_search", "arguments": '{"query":"latest docs","max_results":1}'}
                    ],
                },
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call-2", "name": "web_fetch", "arguments": '{"url":"https://example.test/page"}'}
                    ],
                },
                {"content": "Grounded answer [web:1]", "tool_calls": []},
            ]
        )
        runner = ChatResearchRunner(
            model_factory=lambda _model_name: model,
            model_candidates=lambda requested: [requested],
            web_tools_factory=lambda query: __import__("chat_web_tools").WebResearchTools(connector, relevance_query=query),
        )

        runner.run(
            prompt="latest docs",
            requested_model="zai:glm-4.5-flash",
            history=[],
            system_prompt="Chat system",
            generation={"max_tokens": 300},
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )

        self.assertEqual(
            [event[0] for event in events],
            ["tool_started", "tool_execution", "tool_started", "tool_execution"],
        )
        self.assertEqual(events[0][1]["tool_name"], "web_search")
        self.assertEqual(events[0][1]["arguments"]["query"], "latest docs")
        self.assertEqual(events[2][1]["tool_name"], "web_fetch")
        self.assertEqual(events[2][1]["arguments"]["url"], "https://example.test/page")

    def test_extra_system_messages_are_inserted_per_attempt_and_evidence_corpus_is_returned(self):
        connector = FakeConnector()
        connector.pages["https://example.test/page"] = """
        <html><head><title>Evidence</title></head><body>
          <p>Fetched prose evidence.</p>
          <table><tr><th>Name</th><th>Value</th></tr><tr><td>Metric</td><td>42</td></tr></table>
        </body></html>
        """
        first_model = FakeToolModel(error=RuntimeError("first failed"))
        second_model = FakeToolModel(
            [
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call-1", "name": "web_fetch", "arguments": '{"url":"https://example.test/page"}'}
                    ],
                },
                {"content": "Final answer [web:1]", "tool_calls": []},
            ]
        )
        models = {"model-a": first_model, "model-b": second_model}
        extra_messages = [{"role": "system", "content": "Route, memory, and attachment context"}]
        runner = ChatResearchRunner(
            model_factory=lambda model_name: models[model_name],
            model_candidates=lambda _requested: ["model-a", "model-b"],
            web_tools_factory=lambda query: __import__("chat_web_tools").WebResearchTools(connector, relevance_query=query),
        )

        result = runner.run(
            prompt="metric",
            requested_model="model-a",
            history=[],
            system_prompt="Chat system",
            generation={"max_tokens": 300},
            extra_system_messages=extra_messages,
        )

        self.assertEqual(result.used_model, "model-b")
        first_messages = first_model.requests[0]["messages"]
        second_messages = second_model.requests[0]["messages"]
        self.assertEqual(first_messages[0], {"role": "system", "content": "Chat system"})
        self.assertEqual(first_messages[1], extra_messages[0])
        self.assertEqual(second_messages[0], {"role": "system", "content": "Chat system"})
        self.assertEqual(second_messages[1], extra_messages[0])
        self.assertIn("Fetched prose evidence", result.evidence_corpus)
        self.assertIn("Metric: 42", result.evidence_corpus)

    def test_force_final_answer_uses_best_effort_turn_after_research_limit(self):
        connector = FakeConnector()
        connector.pages["https://example.test/page"] = """
        <html><head><title>Evidence</title></head><body>
          <p>Fetched evidence.</p>
        </body></html>
        """
        finalized = []
        model = FakeToolModel(
            [
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call-1", "name": "web_fetch", "arguments": '{"url":"https://example.test/page"}'}
                    ],
                },
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call-2", "name": "web_fetch", "arguments": '{"url":"https://example.test/page"}'}
                    ],
                },
                {"content": "Best effort from fetched evidence [web:1].", "tool_calls": []},
            ]
        )
        runner = ChatResearchRunner(
            model_factory=lambda _model_name: model,
            model_candidates=lambda requested: [requested],
            web_tools_factory=lambda query: __import__("chat_web_tools").WebResearchTools(connector, relevance_query=query),
            max_iterations=2,
            force_final_answer=True,
        )

        result = runner.run(
            prompt="latest docs",
            requested_model="zai:glm-4.5-flash",
            history=[],
            system_prompt="Chat system",
            generation={"max_tokens": 300},
            before_finalize=lambda content, _tools: finalized.append(content) or None,
        )

        self.assertEqual(result.outcome.answer, "Best effort from fetched evidence [web:1].")
        self.assertTrue(result.outcome.used_tools)
        self.assertTrue(result.outcome.forced)
        self.assertEqual(connector.fetches, ["https://example.test/page"])
        self.assertEqual(model.requests[-1]["tools"], [])
        self.assertIn("research limit", model.requests[-1]["messages"][-1]["content"])
        self.assertEqual(finalized, ["Best effort from fetched evidence [web:1]."])

    def test_web_fetch_unproductive_results_add_chat_steering(self):
        connector = FakeConnector()
        connector.pages["https://example.test/blocked-a"] = "<html><body></body></html>"
        connector.pages["https://example.test/blocked-b"] = "<html><body></body></html>"
        model = FakeToolModel(
            [
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call-1", "name": "web_fetch", "arguments": '{"url":"https://example.test/blocked-a"}'}
                    ],
                },
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call-2", "name": "web_fetch", "arguments": '{"url":"https://example.test/blocked-b"}'}
                    ],
                },
                {"content": "No usable evidence found.", "tool_calls": []},
            ]
        )
        runner = ChatResearchRunner(
            model_factory=lambda _model_name: model,
            model_candidates=lambda requested: [requested],
            web_tools_factory=lambda query: __import__("chat_web_tools").WebResearchTools(connector, relevance_query=query),
        )

        runner.run(
            prompt="latest docs",
            requested_model="zai:glm-4.5-flash",
            history=[],
            system_prompt="Chat system",
            generation={"max_tokens": 300},
        )

        self.assertEqual(connector.fetches, ["https://example.test/blocked-a", "https://example.test/blocked-b"])
        steering_message = model.requests[2]["messages"][-1]
        self.assertEqual(steering_message["role"], "user")
        self.assertIn("returned no usable data", steering_message["content"])

    def test_parallel_web_fetch_fanout_keeps_source_order_stable(self):
        connector = SlowConnector()
        for name in ("a", "b", "c"):
            connector.pages[f"https://example.test/{name}"] = f"""
            <html><head><title>{name.upper()}</title></head><body>
              <p>Evidence {name.upper()}.</p>
            </body></html>
            """
        model = FakeToolModel(
            [
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call-a", "name": "web_fetch", "arguments": '{"url":"https://example.test/a"}'},
                        {"id": "call-b", "name": "web_fetch", "arguments": '{"url":"https://example.test/b"}'},
                        {"id": "call-c", "name": "web_fetch", "arguments": '{"url":"https://example.test/c"}'},
                    ],
                },
                {"content": "Fetched all sources [web:1] [web:2] [web:3].", "tool_calls": []},
            ]
        )
        runner = ChatResearchRunner(
            model_factory=lambda _model_name: model,
            model_candidates=lambda requested: [requested],
            web_tools_factory=lambda query: __import__("chat_web_tools").WebResearchTools(connector, relevance_query=query),
        )

        started = time.perf_counter()
        result = runner.run(
            prompt="latest docs",
            requested_model="zai:glm-4.5-flash",
            history=[],
            system_prompt="Chat system",
            generation={"max_tokens": 300},
        )
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.45)
        tool_messages = [message for message in model.requests[1]["messages"] if message.get("role") == "tool"]
        self.assertEqual([message["tool_call_id"] for message in tool_messages], ["call-a", "call-b", "call-c"])
        self.assertEqual([json.loads(message["content"])["index"] for message in tool_messages], [1, 2, 3])
        self.assertEqual([source["url"] for source in result.sources], [
            "https://example.test/a",
            "https://example.test/b",
            "https://example.test/c",
        ])


if __name__ == "__main__":
    unittest.main()
