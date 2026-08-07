import json
import time
import unittest

from tool_loop import LoopHooks, run_tool_loop


class FakeModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def complete(self, messages, tools, generation=None):
        self.requests.append({"messages": list(messages), "tools": list(tools), "generation": generation})
        return self.responses.pop(0)


class StreamingFakeModel(FakeModel):
    def stream_complete(self, messages, tools, generation=None, on_delta=None):
        response = self.complete(messages, tools, generation)
        for delta in response.get("stream_deltas", []):
            if on_delta:
                on_delta(delta)
        return response


class FakeTools:
    schemas = [{"type": "function", "function": {"name": "read_file"}}]

    def __init__(self):
        self.calls = []

    def dispatch(self, name, arguments):
        self.calls.append((name, arguments))
        return json.dumps({"status": "ok", "content": "tool-result"}, ensure_ascii=False)


class LargeResultTools(FakeTools):
    def dispatch(self, name, arguments):
        self.calls.append((name, arguments))
        return json.dumps(
            {"status": "ok", "content": str(arguments["label"]) * int(arguments["size"])},
            ensure_ascii=False,
        )


class SlowTools(FakeTools):
    def dispatch(self, name, arguments):
        delay = float(arguments.get("delay", 0))
        time.sleep(delay)
        self.calls.append((name, arguments))
        return json.dumps({"status": "ok", "content": arguments["value"]}, ensure_ascii=False)


class StrictTwoArgModel:
    def __init__(self):
        self.requests = []

    def complete(self, messages, tools):
        self.requests.append({"messages": list(messages), "tools": list(tools)})
        return {"content": "done", "tool_calls": []}


class ToolLoopTests(unittest.TestCase):
    def test_generation_is_forwarded_to_model_complete(self):
        model = FakeModel([{"content": "done", "tool_calls": []}])

        outcome = run_tool_loop(
            model=model,
            messages=[{"role": "user", "content": "answer"}],
            tools=FakeTools(),
            max_iterations=2,
            generation={"temperature": 0.2, "max_tokens": 512},
        )

        self.assertEqual(outcome.answer, "done")
        self.assertEqual(model.requests[0]["generation"], {"temperature": 0.2, "max_tokens": 512})

    def test_absent_generation_is_forwarded_as_none(self):
        model = FakeModel([{"content": "done", "tool_calls": []}])

        run_tool_loop(
            model=model,
            messages=[{"role": "user", "content": "answer"}],
            tools=FakeTools(),
            max_iterations=2,
        )

        self.assertIsNone(model.requests[0]["generation"])

    def test_absent_generation_preserves_two_argument_model_call(self):
        model = StrictTwoArgModel()

        outcome = run_tool_loop(
            model=model,
            messages=[{"role": "user", "content": "answer"}],
            tools=FakeTools(),
            max_iterations=2,
        )

        self.assertEqual(outcome.answer, "done")
        self.assertEqual(len(model.requests), 1)

    def test_dispatches_tool_calls_and_returns_final_answer(self):
        model = FakeModel(
            [
                {
                    "content": None,
                    "tool_calls": [
                        {"id": "call-1", "name": "read_file", "arguments": '{"path":"README.md"}'}
                    ],
                },
                {"content": "final answer", "tool_calls": []},
            ]
        )
        tools = FakeTools()
        events = []
        hook_results = []

        hooks = LoopHooks(on_tool_result=lambda name, arguments, result: hook_results.append((name, arguments, result)))

        outcome = run_tool_loop(
            model=model,
            messages=[{"role": "user", "content": "read"}],
            tools=tools,
            max_iterations=4,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
            hooks=hooks,
        )

        self.assertEqual(outcome.answer, "final answer")
        self.assertTrue(outcome.used_tools)
        self.assertEqual(outcome.iterations, 2)
        self.assertEqual(tools.calls, [("read_file", {"path": "README.md"})])
        tool_message = model.requests[1]["messages"][-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertEqual(tool_message["tool_call_id"], "call-1")
        self.assertIn("tool-result", tool_message["content"])
        self.assertEqual(hook_results[0][0], "read_file")
        self.assertEqual(events[0][0], "tool_execution")

    def test_duplicate_tool_call_is_skipped_without_dispatching_again(self):
        duplicate_call = {"id": "call-1", "name": "read_file", "arguments": '{"path":"README.md"}'}
        model = FakeModel(
            [
                {"content": None, "tool_calls": [duplicate_call]},
                {"content": None, "tool_calls": [{**duplicate_call, "id": "call-2"}]},
                {"content": "final answer from prior result", "tool_calls": []},
            ]
        )
        tools = FakeTools()
        events = []
        hook_results = []

        outcome = run_tool_loop(
            model=model,
            messages=[{"role": "user", "content": "read twice"}],
            tools=tools,
            max_iterations=4,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
            hooks=LoopHooks(on_tool_result=lambda name, arguments, result: hook_results.append((name, arguments, result))),
        )

        self.assertEqual(outcome.answer, "final answer from prior result")
        self.assertEqual(tools.calls, [("read_file", {"path": "README.md"})])
        skipped_tool_message = model.requests[2]["messages"][-1]
        self.assertEqual(skipped_tool_message["role"], "tool")
        self.assertEqual(skipped_tool_message["tool_call_id"], "call-2")
        skipped_payload = json.loads(skipped_tool_message["content"])
        self.assertEqual(skipped_payload["status"], "skipped")
        self.assertIn("duplicate", skipped_payload["reason"])
        self.assertEqual([event[1]["tool_name"] for event in events], ["read_file", "read_file"])
        self.assertEqual(json.loads(events[1][1]["result"])["status"], "skipped")
        self.assertEqual(json.loads(hook_results[1][2])["status"], "skipped")

    def test_unproductive_tool_results_inject_steering_once_when_opted_in(self):
        model = FakeModel(
            [
                {
                    "content": None,
                    "tool_calls": [
                        {"id": "call-1", "name": "read_file", "arguments": '{"path":"a.txt"}'}
                    ],
                },
                {
                    "content": None,
                    "tool_calls": [
                        {"id": "call-2", "name": "read_file", "arguments": '{"path":"b.txt"}'}
                    ],
                },
                {"content": "final answer after steering", "tool_calls": []},
            ]
        )
        tools = FakeTools()

        def unproductive(_name, _arguments, _result):
            return True

        outcome = run_tool_loop(
            model=model,
            messages=[{"role": "user", "content": "find data"}],
            tools=tools,
            max_iterations=4,
            unproductive_result_detector=unproductive,
            unproductive_steering_threshold=2,
        )

        self.assertEqual(outcome.answer, "final answer after steering")
        self.assertEqual(len(tools.calls), 2)
        steering_message = model.requests[2]["messages"][-1]
        self.assertEqual(steering_message["role"], "user")
        self.assertIn("returned no usable data", steering_message["content"])
        self.assertIn("state what is missing", steering_message["content"])

    def test_productive_tool_result_resets_unproductive_steering_counter(self):
        model = FakeModel(
            [
                {
                    "content": None,
                    "tool_calls": [
                        {"id": "call-1", "name": "read_file", "arguments": '{"path":"a.txt"}'}
                    ],
                },
                {
                    "content": None,
                    "tool_calls": [
                        {"id": "call-2", "name": "read_file", "arguments": '{"path":"b.txt"}'}
                    ],
                },
                {
                    "content": None,
                    "tool_calls": [
                        {"id": "call-3", "name": "read_file", "arguments": '{"path":"c.txt"}'}
                    ],
                },
                {"content": "final answer", "tool_calls": []},
            ]
        )
        sequence = iter([True, False, True])

        run_tool_loop(
            model=model,
            messages=[{"role": "user", "content": "find data"}],
            tools=FakeTools(),
            max_iterations=5,
            unproductive_result_detector=lambda _name, _arguments, _result: next(sequence),
            unproductive_steering_threshold=2,
        )

        self.assertNotIn("returned no usable data", json.dumps(model.requests[-1]["messages"]))

    def test_tool_context_budget_compresses_oldest_tool_results(self):
        model = FakeModel(
            [
                {
                    "content": None,
                    "tool_calls": [
                        {"id": "call-1", "name": "read_file", "arguments": '{"label":"A","size":200}'}
                    ],
                },
                {
                    "content": None,
                    "tool_calls": [
                        {"id": "call-2", "name": "read_file", "arguments": '{"label":"B","size":80}'}
                    ],
                },
                {"content": "final answer", "tool_calls": []},
            ]
        )

        outcome = run_tool_loop(
            model=model,
            messages=[{"role": "user", "content": "read lots"}],
            tools=LargeResultTools(),
            max_iterations=4,
            tool_context_budget_chars=260,
        )

        self.assertEqual(outcome.answer, "final answer")
        tool_messages = [message for message in model.requests[2]["messages"] if message.get("role") == "tool"]
        self.assertEqual(len(tool_messages), 2)
        self.assertEqual(json.loads(tool_messages[0]["content"])["status"], "truncated")
        self.assertEqual(json.loads(tool_messages[1]["content"])["status"], "ok")
        self.assertLessEqual(sum(len(message["content"]) for message in tool_messages), 260)

    def test_parallel_tool_dispatch_runs_concurrently_and_preserves_message_order(self):
        model = FakeModel(
            [
                {
                    "content": None,
                    "tool_calls": [
                        {"id": "call-1", "name": "read_file", "arguments": '{"value":"one","delay":0.2}'},
                        {"id": "call-2", "name": "read_file", "arguments": '{"value":"two","delay":0.2}'},
                        {"id": "call-3", "name": "read_file", "arguments": '{"value":"three","delay":0.2}'},
                    ],
                },
                {"content": "final answer", "tool_calls": []},
            ]
        )
        tools = SlowTools()
        started = time.perf_counter()

        outcome = run_tool_loop(
            model=model,
            messages=[{"role": "user", "content": "fan out"}],
            tools=tools,
            max_iterations=3,
            parallel_tools=True,
        )
        elapsed = time.perf_counter() - started

        self.assertEqual(outcome.answer, "final answer")
        self.assertLess(elapsed, 0.45)
        tool_messages = [message for message in model.requests[1]["messages"] if message.get("role") == "tool"]
        self.assertEqual([message["tool_call_id"] for message in tool_messages], ["call-1", "call-2", "call-3"])
        self.assertEqual([json.loads(message["content"])["content"] for message in tool_messages], ["one", "two", "three"])

    def test_streams_live_and_resets_discarded_tool_turn(self):
        model = StreamingFakeModel(
            [
                {
                    "content": None,
                    "stream_deltas": ["should ", "not stream"],
                    "tool_calls": [
                        {"id": "call-1", "name": "read_file", "arguments": '{"path":"README.md"}'}
                    ],
                },
                {"content": "final answer", "stream_deltas": ["final ", "answer"], "tool_calls": []},
            ]
        )
        deltas = []
        resets = []

        outcome = run_tool_loop(
            model=model,
            messages=[{"role": "user", "content": "read"}],
            tools=FakeTools(),
            max_iterations=4,
            on_final_delta=deltas.append,
            on_stream_reset=lambda: resets.append("reset"),
        )

        self.assertEqual(outcome.answer, "final answer")
        self.assertEqual(deltas, ["should ", "not stream", "final ", "answer"])
        self.assertEqual(resets, ["reset"])

    def test_stream_delta_is_emitted_during_model_turn(self):
        checkpoints = []
        model = StreamingFakeModel(
            [{"content": "live answer", "stream_deltas": ["live ", "answer"], "tool_calls": []}],
        )
        deltas = []

        def on_delta(delta):
            deltas.append(delta)
            checkpoints.append(("inside-stream", list(deltas)))

        outcome = run_tool_loop(
            model=model,
            messages=[{"role": "user", "content": "stream"}],
            tools=FakeTools(),
            max_iterations=2,
            on_final_delta=on_delta,
        )

        self.assertEqual(outcome.answer, "live answer")
        self.assertEqual(deltas, ["live ", "answer"])
        self.assertEqual(checkpoints[0], ("inside-stream", ["live "]))

    def test_before_finalize_hook_can_request_repair_turn(self):
        model = FakeModel(
            [
                {"content": "premature final", "tool_calls": []},
                {"content": "verified final", "tool_calls": []},
            ]
        )
        repair_messages = []

        def before_finalize(content):
            if content == "premature final":
                repair_messages.append(content)
                return "Run verification before reporting."
            return None

        outcome = run_tool_loop(
            model=model,
            messages=[{"role": "user", "content": "work"}],
            tools=FakeTools(),
            max_iterations=4,
            hooks=LoopHooks(before_finalize=before_finalize),
        )

        self.assertEqual(outcome.answer, "verified final")
        self.assertFalse(outcome.used_tools)
        self.assertEqual(repair_messages, ["premature final"])
        self.assertEqual(model.requests[1]["messages"][-1], {"role": "user", "content": "Run verification before reporting."})

    def test_empty_response_recovers_once(self):
        model = FakeModel(
            [
                {"content": "", "tool_calls": []},
                {"content": "recovered", "tool_calls": []},
            ]
        )
        events = []

        outcome = run_tool_loop(
            model=model,
            messages=[{"role": "user", "content": "continue"}],
            tools=FakeTools(),
            max_iterations=3,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )

        self.assertEqual(outcome.answer, "recovered")
        self.assertEqual(model.requests[1]["messages"][-1]["role"], "user")
        self.assertIn("previous response was empty", model.requests[1]["messages"][-1]["content"])
        self.assertIn(("model_empty_response", {"retry": 1}), events)

    def test_force_final_answer_after_iteration_limit_uses_no_tools_and_finalize_hook(self):
        model = FakeModel(
            [
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call-1", "name": "read_file", "arguments": '{"path":"a.txt"}'}
                    ],
                },
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call-2", "name": "read_file", "arguments": '{"path":"b.txt"}'}
                    ],
                },
                {"content": "best effort from gathered evidence", "tool_calls": []},
            ]
        )
        seen_finalize = []

        outcome = run_tool_loop(
            model=model,
            messages=[{"role": "user", "content": "research"}],
            tools=FakeTools(),
            max_iterations=2,
            force_final_answer=True,
            hooks=LoopHooks(before_finalize=lambda content: seen_finalize.append(content) or None),
        )

        self.assertEqual(outcome.answer, "best effort from gathered evidence")
        self.assertTrue(outcome.used_tools)
        self.assertTrue(outcome.forced)
        self.assertEqual(outcome.iterations, 2)
        self.assertEqual(model.requests[-1]["tools"], [])
        self.assertIn("research limit", model.requests[-1]["messages"][-1]["content"])
        self.assertIn("do NOT guess", model.requests[-1]["messages"][-1]["content"])
        self.assertEqual(seen_finalize, ["best effort from gathered evidence"])

    def test_force_final_answer_default_false_still_raises_on_iteration_limit(self):
        model = FakeModel(
            [
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call-1", "name": "read_file", "arguments": '{"path":"a.txt"}'}
                    ],
                }
            ]
        )

        with self.assertRaisesRegex(RuntimeError, "exceeded 1 iterations"):
            run_tool_loop(
                model=model,
                messages=[{"role": "user", "content": "research"}],
                tools=FakeTools(),
                max_iterations=1,
            )


if __name__ == "__main__":
    unittest.main()
