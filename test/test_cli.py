from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

from cli import CliDependencies, _command_approval_adapter, main
from developer_tools import CommandProposal, DeveloperTools, VerificationCommand
from workspace_tools import WorkspaceTools


class FakeModel:
    def __init__(self, answers):
        self.answers = iter(answers)

    def complete(self, messages, tools):
        return {"content": next(self.answers), "tool_calls": []}


class ToolCallingModel:
    def __init__(self):
        self.requests = []

    def complete(self, messages, tools):
        self.requests.append({"messages": list(messages), "tools": list(tools)})
        if len(self.requests) == 1:
            return {
                "content": None,
                "tool_calls": [
                    {
                        "id": "write-call",
                        "name": "write_file",
                        "arguments": '{"path":"notes.txt","content":"hello audit\\n"}',
                    }
                ],
            }
        if len(self.requests) == 2:
            return {"content": "audit complete before verification", "tool_calls": []}
        if len(self.requests) == 3:
            return {
                "content": None,
                "tool_calls": [
                    {
                        "id": "verify-call",
                        "name": "run_verification",
                        "arguments": '{"name":"python-tests"}',
                    }
                ],
            }
        return {"content": "audit complete", "tool_calls": []}


class NullRecorder:
    def start(self, model, workspace):
        pass

    def record(self, event_type, payload):
        pass

    def finish(self, status, summary):
        pass


class CliTests(unittest.TestCase):
    def test_one_shot_prompt_prints_answer(self):
        stdout = StringIO()
        stderr = StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            dependencies = CliDependencies(
                stdout=stdout,
                stderr=stderr,
                input_fn=lambda prompt: "",
                model_factory=lambda config: FakeModel(["Standalone answer"]),
                model_lister=lambda config: ["test/model"],
                recorder_factory=NullRecorder,
            )

            exit_code = main(
                ["--workspace", temp_dir, "--prompt", "hello"],
                dependencies=dependencies,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "Standalone answer\n")
        self.assertEqual(stderr.getvalue(), "")

    def test_list_models_prints_local_namespace(self):
        stdout = StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            dependencies = CliDependencies(
                stdout=stdout,
                stderr=StringIO(),
                input_fn=lambda prompt: "",
                model_factory=lambda config: FakeModel([]),
                model_lister=lambda config: ["alpha", "beta"],
                recorder_factory=NullRecorder,
            )

            exit_code = main(
                ["--workspace", temp_dir, "--list-models"],
                dependencies=dependencies,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "local:alpha\nlocal:beta\n")

    def test_interactive_mode_handles_clear_and_exit(self):
        stdout = StringIO()
        inputs = iter(["first", "/clear", "second", "/exit"])
        with tempfile.TemporaryDirectory() as temp_dir:
            dependencies = CliDependencies(
                stdout=stdout,
                stderr=StringIO(),
                input_fn=lambda prompt: next(inputs),
                model_factory=lambda config: FakeModel(["one", "two"]),
                model_lister=lambda config: [],
                recorder_factory=NullRecorder,
            )

            exit_code = main(["--workspace", temp_dir], dependencies=dependencies)

        self.assertEqual(exit_code, 0)
        self.assertIn("one\n", stdout.getvalue())
        self.assertIn("History cleared.\n", stdout.getvalue())
        self.assertIn("two\n", stdout.getvalue())

    def test_model_connection_error_is_concise(self):
        stderr = StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            dependencies = CliDependencies(
                stdout=StringIO(),
                stderr=stderr,
                input_fn=lambda prompt: "",
                model_factory=lambda config: FakeModel([]),
                model_lister=lambda config: (_ for _ in ()).throw(RuntimeError("server offline")),
                recorder_factory=NullRecorder,
            )

            exit_code = main(
                ["--workspace", temp_dir, "--list-models"],
                dependencies=dependencies,
            )

        self.assertEqual(exit_code, 1)
        self.assertEqual(stderr.getvalue(), "Cowork error: server offline\n")

    def test_command_approval_displays_exact_allowlisted_process(self):
        stderr = StringIO()
        dependencies = CliDependencies(
            stdout=StringIO(),
            stderr=stderr,
            input_fn=lambda prompt: "yes",
        )
        proposal = CommandProposal(
            name="python-tests",
            argv=("python.exe", "-m", "unittest", "discover"),
            cwd=r"C:\work tree",
            timeout_seconds=120,
        )

        approved = _command_approval_adapter(
            SimpleNamespace(auto_approve=False),
            dependencies,
        )(proposal)

        self.assertTrue(approved)
        output = stderr.getvalue()
        self.assertIn("Verification preset: python-tests", output)
        self.assertIn(r"Working directory: C:\work tree", output)
        self.assertIn("python.exe -m unittest discover", output)
        self.assertIn("Timeout: 120 seconds", output)

    def test_cli_wires_workspace_audit_events_to_session_store(self):
        events = []
        stdout = StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            dependencies = CliDependencies(
                stdout=stdout,
                stderr=StringIO(),
                input_fn=lambda prompt: "yes",
                model_factory=lambda config: ToolCallingModel(),
                model_lister=lambda config: [],
                recorder_factory=NullRecorder,
            )

            def workspace_tools_factory(root, approve_write, approve_command, audit_sink):
                developer_tools = DeveloperTools(
                    root,
                    approve_command=approve_command,
                    verification_commands={
                        "python-tests": VerificationCommand(
                            name="python-tests",
                            argv=(sys.executable, "-c", "print('ok')"),
                            timeout_seconds=5,
                        )
                    },
                    audit_sink=audit_sink,
                )
                return WorkspaceTools(
                    root,
                    approve_write=approve_write,
                    approve_command=approve_command,
                    developer_tools=developer_tools,
                    audit_sink=audit_sink,
                )

            with (
                patch("cli.record_cowork_event", lambda event_type, payload: events.append((event_type, payload))),
                patch("cli.WorkspaceTools", workspace_tools_factory),
            ):
                exit_code = main(
                    ["--workspace", temp_dir, "--prompt", "write a note"],
                    dependencies=dependencies,
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "audit complete\n")
        self.assertIn("write_approval_requested", [event_type for event_type, _payload in events])
        self.assertIn("write_approval_decision", [event_type for event_type, _payload in events])
        self.assertIn("file_written", [event_type for event_type, _payload in events])


if __name__ == "__main__":
    unittest.main()
