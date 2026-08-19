from pathlib import Path
import sys
import tempfile
import unittest

import cowork_agent
from agent_state import AgentRunState
from cowork_agent import CoworkAgent, OpenAIChatModel
from developer_tools import DeveloperTools, VerificationCommand
from workspace_tools import WorkspaceTools


class FakeModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def complete(self, messages, tools):
        self.requests.append({"messages": list(messages), "tools": list(tools)})
        return self.responses.pop(0)


class FakeRecorder:
    def __init__(self):
        self.events = []
        self.finished = []

    def start(self, model, workspace):
        self.events.append(("start", {"model": model, "workspace": str(workspace)}))

    def record(self, event_type, payload):
        self.events.append((event_type, payload))

    def finish(self, status, summary):
        self.finished.append((status, summary))


class FakeOpenAIMessage:
    content = "ok"
    tool_calls = []


class FakeOpenAIChoice:
    message = FakeOpenAIMessage()


class FakeOpenAIResponse:
    choices = [FakeOpenAIChoice()]


class FakeCompletions:
    def __init__(self):
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return FakeOpenAIResponse()


class FakeOpenAIClient:
    def __init__(self):
        self.completions = FakeCompletions()
        self.chat = type("Chat", (), {"completions": self.completions})()


class FakeStreamingDelta:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class FakeStreamingChoice:
    def __init__(self, delta):
        self.delta = delta


class FakeStreamingChunk:
    def __init__(self, delta):
        self.choices = [FakeStreamingChoice(delta)]


class FakeStreamingCompletions(FakeCompletions):
    def create(self, **kwargs):
        self.requests.append(kwargs)
        if kwargs.get("stream"):
            return [
                FakeStreamingChunk(FakeStreamingDelta("Hello ")),
                FakeStreamingChunk(FakeStreamingDelta("world")),
            ]
        return FakeOpenAIResponse()


class FakeStreamingClient(FakeOpenAIClient):
    def __init__(self):
        self.completions = FakeStreamingCompletions()
        self.chat = type("Chat", (), {"completions": self.completions})()


class CoworkAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        (self.workspace / "README.md").write_text("# Standalone\n", encoding="utf-8")
        self.tools = WorkspaceTools(self.workspace, approve_write=lambda proposal: True)
        self.recorder = FakeRecorder()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_openai_chat_model_strips_provider_prefix_and_sends_extra_body(self):
        fake_client = FakeOpenAIClient()
        captured_timeout = []
        original_factory = cowork_agent.create_local_ai_client
        def fake_factory(_base_url, _api_key, timeout=45.0):
            captured_timeout.append(timeout)
            return fake_client
        cowork_agent.create_local_ai_client = fake_factory
        try:
            model = OpenAIChatModel(
                "https://api.z.ai/api/paas/v4",
                "secret",
                "zai:glm-4.7-flash",
                extra_body={"thinking": {"type": "disabled"}},
            )

            result = model.complete([{"role": "user", "content": "hello"}], tools=[])
        finally:
            cowork_agent.create_local_ai_client = original_factory

        self.assertEqual(result["content"], "ok")
        self.assertEqual(captured_timeout, [45.0])
        self.assertEqual(fake_client.completions.requests[0]["model"], "glm-4.7-flash")
        self.assertEqual(fake_client.completions.requests[0]["extra_body"], {"thinking": {"type": "disabled"}})

    def test_openai_chat_model_stream_complete_yields_deltas_and_final_text(self):
        fake_client = FakeStreamingClient()
        original_factory = cowork_agent.create_local_ai_client
        cowork_agent.create_local_ai_client = lambda _base_url, _api_key, timeout=45.0: fake_client
        try:
            model = OpenAIChatModel("http://127.0.0.1:1234/v1", "secret", "local:test")
            deltas = []

            result = model.stream_complete(
                [{"role": "user", "content": "hello"}],
                tools=[],
                generation={"temperature": 0.3, "max_tokens": 64},
                on_delta=deltas.append,
            )
        finally:
            cowork_agent.create_local_ai_client = original_factory

        self.assertEqual(result, {"content": "Hello world", "tool_calls": []})
        self.assertEqual(deltas, ["Hello ", "world"])
        self.assertTrue(fake_client.completions.requests[0]["stream"])
        self.assertEqual(fake_client.completions.requests[0]["temperature"], 0.3)
        self.assertEqual(fake_client.completions.requests[0]["max_tokens"], 64)

    def test_executes_tool_calls_and_returns_final_text(self):
        model = FakeModel(
            [
                {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "name": "read_file",
                            "arguments": '{"path":"README.md"}',
                        }
                    ],
                },
                {"content": "Repository inspected.", "tool_calls": []},
            ]
        )
        agent = CoworkAgent(
            model=model,
            model_name="local:test-model",
            workspace=self.workspace,
            tools=self.tools,
            recorder=self.recorder,
            max_iterations=4,
        )
        statuses = []

        reply = agent.run("Read the repository overview", on_status=statuses.append)

        self.assertEqual(reply, "Repository inspected.")
        tool_message = model.requests[1]["messages"][-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertEqual(tool_message["tool_call_id"], "call-1")
        self.assertIn("# Standalone", tool_message["content"])
        self.assertEqual(self.recorder.finished, [("completed", "Repository inspected.")])
        self.assertEqual(
            statuses,
            [
                "Inspecting project context...",
                "Planning the next action...",
                "Reading README.md...",
                "Reviewing read_file result...",
                "Writing the final response...",
            ],
        )

    def test_requires_verification_after_write_before_final_report(self):
        model = FakeModel(
            [
                {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "write-1",
                            "name": "write_file",
                            "arguments": '{"path":"notes.txt","content":"hello\\n"}',
                        }
                    ],
                },
                {"content": "Implementation complete without tests.", "tool_calls": []},
                {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "verify-1",
                            "name": "run_verification",
                            "arguments": '{"name":"python-tests"}',
                        }
                    ],
                },
                {"content": "Implementation complete with verification.", "tool_calls": []},
            ]
        )
        developer_tools = DeveloperTools(
            self.workspace,
            approve_command=lambda proposal: True,
            verification_commands={
                "python-tests": VerificationCommand(
                    name="python-tests",
                    argv=(sys.executable, "-c", "print('ok')"),
                    timeout_seconds=5,
                )
            },
        )
        tools = WorkspaceTools(
            self.workspace,
            approve_write=lambda proposal: True,
            approve_command=lambda proposal: True,
            developer_tools=developer_tools,
        )
        agent = CoworkAgent(
            model=model,
            model_name="local:test-model",
            workspace=self.workspace,
            tools=tools,
            recorder=self.recorder,
            max_iterations=6,
        )

        reply = agent.run("Write a note and verify it")

        self.assertEqual(reply, "Implementation complete with verification.")
        repair_message = model.requests[2]["messages"][-1]
        self.assertEqual(repair_message["role"], "user")
        self.assertIn("run_verification", repair_message["content"])
        event_types = [event_type for event_type, _payload in self.recorder.events]
        self.assertIn("agent_stage", event_types)
        stages = [payload["stage"] for event_type, payload in self.recorder.events if event_type == "agent_stage"]
        self.assertEqual(stages, ["inspect", "plan", "act", "verify", "report"])
        evidence_events = [
            payload for event_type, payload in self.recorder.events if event_type == "completion_evidence"
        ]
        self.assertEqual(
            evidence_events[-1],
            {
                "writes_performed": True,
                "verification_observed": True,
                "verification_passed": True,
                "verification_statuses": ["passed"],
                "verification_runs": [{"name": "python-tests", "status": "passed"}],
                "test_files_modified": [],
            },
        )

    def test_resumed_state_with_prior_write_requires_verification_before_report(self):
        resumed_state = AgentRunState()
        resumed_state.observe_tool_result("write_file", '{"status":"written","path":"notes.txt"}')
        model = FakeModel(
            [
                {"content": "Premature report", "tool_calls": []},
                {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "verify-1",
                            "name": "run_verification",
                            "arguments": '{"name":"python-tests"}',
                        }
                    ],
                },
                {"content": "Resumed task verified.", "tool_calls": []},
            ]
        )
        developer_tools = DeveloperTools(
            self.workspace,
            approve_command=lambda proposal: True,
            verification_commands={
                "python-tests": VerificationCommand(
                    name="python-tests",
                    argv=(sys.executable, "-c", "print('ok')"),
                    timeout_seconds=5,
                )
            },
        )
        tools = WorkspaceTools(
            self.workspace,
            approve_write=lambda proposal: True,
            approve_command=lambda proposal: True,
            developer_tools=developer_tools,
        )
        agent = CoworkAgent(
            model=model,
            model_name="local:test-model",
            workspace=self.workspace,
            tools=tools,
            recorder=self.recorder,
            max_iterations=5,
        )

        reply = agent.run("resume previous task", initial_run_state=resumed_state)

        self.assertEqual(reply, "Resumed task verified.")
        repair_message = model.requests[1]["messages"][-1]
        self.assertEqual(repair_message["role"], "user")
        self.assertIn("run_verification", repair_message["content"])
        evidence_events = [
            payload for event_type, payload in self.recorder.events if event_type == "completion_evidence"
        ]
        self.assertTrue(evidence_events[-1]["verification_passed"])
        snapshot_events = [
            payload for event_type, payload in self.recorder.events if event_type == "agent_state_snapshot"
        ]
        self.assertTrue(snapshot_events)
        self.assertTrue(snapshot_events[-1]["verification_passed"])

    def test_invalid_tool_arguments_are_returned_to_the_model(self):
        model = FakeModel(
            [
                {
                    "content": None,
                    "tool_calls": [
                        {"id": "bad-call", "name": "read_file", "arguments": "not-json"}
                    ],
                },
                {"content": "Recovered from the tool error.", "tool_calls": []},
            ]
        )
        agent = CoworkAgent(
            model=model,
            model_name="local:test-model",
            workspace=self.workspace,
            tools=self.tools,
            recorder=self.recorder,
            max_iterations=4,
        )
        statuses = []

        reply = agent.run("Read a file", on_status=statuses.append)

        self.assertEqual(reply, "Recovered from the tool error.")
        self.assertIn("Invalid tool arguments", model.requests[1]["messages"][-1]["content"])
        self.assertTrue(
            any(status.startswith("read_file error: Invalid tool arguments") for status in statuses),
            statuses,
        )

    def test_returns_best_effort_report_when_tool_limit_is_reached(self):
        repeated_call = {
            "content": None,
            "tool_calls": [
                {"id": "loop", "name": "list_directory", "arguments": '{"path":"."}'}
            ],
        }
        model = FakeModel(
            [
                repeated_call,
                repeated_call,
                {"content": "I could not complete every inspection step, but no changes were made.", "tool_calls": []},
            ]
        )
        agent = CoworkAgent(
            model=model,
            model_name="local:test-model",
            workspace=self.workspace,
            tools=self.tools,
            recorder=self.recorder,
            max_iterations=2,
        )

        reply = agent.run("Loop forever")

        self.assertEqual(reply, "I could not complete every inspection step, but no changes were made.")
        self.assertEqual(model.requests[-1]["tools"], [])
        self.assertIn("research limit", model.requests[-1]["messages"][-1]["content"])
        self.assertEqual(self.recorder.finished[-1], ("completed", reply))

    def test_recovers_once_from_empty_model_response(self):
        model = FakeModel(
            [
                {"content": "", "tool_calls": []},
                {"content": "Recovered answer", "tool_calls": []},
            ]
        )
        agent = CoworkAgent(
            model=model,
            model_name="local:test-model",
            workspace=self.workspace,
            tools=self.tools,
            recorder=self.recorder,
            max_iterations=3,
        )

        reply = agent.run("continue after an empty response")

        self.assertEqual(reply, "Recovered answer")
        repair_message = model.requests[1]["messages"][-1]
        self.assertEqual(repair_message["role"], "user")
        self.assertIn("previous response was empty", repair_message["content"])
        self.assertIn("model_empty_response", [event_type for event_type, _payload in self.recorder.events])

    def test_clear_history_removes_previous_turns(self):
        model = FakeModel(
            [
                {"content": "First answer", "tool_calls": []},
                {"content": "Second answer", "tool_calls": []},
            ]
        )
        agent = CoworkAgent(
            model=model,
            model_name="local:test-model",
            workspace=self.workspace,
            tools=self.tools,
            recorder=self.recorder,
        )

        agent.run("first")
        agent.clear_history()
        agent.run("second")

        second_request = model.requests[1]["messages"]
        self.assertFalse(any(message.get("content") == "first" for message in second_request))

    def test_accepts_multimodal_user_content_without_persisting_image_data_in_history(self):
        model = FakeModel([{"content": "I can see the diagram.", "tool_calls": []}])
        agent = CoworkAgent(
            model=model,
            model_name="openai:gpt-4o",
            workspace=self.workspace,
            tools=self.tools,
            recorder=self.recorder,
        )
        image_data_url = "data:image/png;base64,aW1hZ2UtYnl0ZXM="

        reply = agent.run(
            "Describe the attached diagram",
            user_content=[
                {"type": "text", "text": "Describe the attached diagram"},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        )

        self.assertEqual(reply, "I can see the diagram.")
        self.assertEqual(model.requests[0]["messages"][-1]["content"][0]["text"], "Describe the attached diagram")
        self.assertEqual(model.requests[0]["messages"][-1]["content"][1]["image_url"]["url"], image_data_url)
        self.assertEqual(agent._history[0], {"role": "user", "content": "Describe the attached diagram"})
        self.assertNotIn(image_data_url, str(agent._history))


if __name__ == "__main__":
    unittest.main()
