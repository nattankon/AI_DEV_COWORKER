import json
import sys
import tempfile
import unittest
from pathlib import Path

from chat_code_exec import CodeExecutor, CodeExecutionToolProvider


class CodeExecutionTests(unittest.TestCase):
    def test_run_python_returns_stdout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = CodeExecutor(python_executable=sys.executable, root=Path(temp_dir), timeout_seconds=3)

            result = executor.run_python("print(2 + 3)")

            self.assertEqual(result["status"], "ok")
            self.assertIn("5", result["stdout"])
            self.assertEqual(result["exit_code"], 0)

    def test_run_python_timeout_is_captured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = CodeExecutor(python_executable=sys.executable, root=Path(temp_dir), timeout_seconds=0.2)

            result = executor.run_python("while True:\n    pass")

            self.assertEqual(result["status"], "timeout")

    def test_provider_requires_approval_before_execution(self):
        approvals = []
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = CodeExecutionToolProvider(
                executor=CodeExecutor(python_executable=sys.executable, root=Path(temp_dir), timeout_seconds=3),
                approval_callback=lambda proposal: approvals.append(proposal) or False,
                enabled=True,
            )

            payload = json.loads(provider.dispatch("run_python", {"code": "print('nope')"}))

            self.assertEqual(payload["status"], "denied")
            self.assertEqual(len(approvals), 1)
            self.assertIn("print('nope')", approvals[0]["code"])

    def test_disabled_provider_does_not_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = CodeExecutionToolProvider(
                executor=CodeExecutor(python_executable=sys.executable, root=Path(temp_dir), timeout_seconds=3),
                approval_callback=lambda _proposal: True,
                enabled=False,
            )

            payload = json.loads(provider.dispatch("run_python", {"code": "print('x')"}))

            self.assertEqual(payload["status"], "disabled")

    def test_network_guard_is_reported_as_best_effort_not_isolation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = CodeExecutor(python_executable=sys.executable, root=Path(temp_dir), timeout_seconds=3)

            result = executor.run_python("import socket\nprint('x')")

            self.assertEqual(result["status"], "error")
            self.assertIn("best-effort", result["error"].casefold())
            self.assertEqual(result["network_isolation"], "best_effort_static_check")
            self.assertEqual(result["sandbox_level"], "subprocess_tempdir_experimental")

    def test_approval_proposal_exposes_experimental_sandbox_metadata(self):
        approvals = []
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = CodeExecutionToolProvider(
                executor=CodeExecutor(python_executable=sys.executable, root=Path(temp_dir), timeout_seconds=3),
                approval_callback=lambda proposal: approvals.append(proposal) or False,
                enabled=True,
            )

            provider.dispatch("run_python", {"code": "print('inspect metadata')"})

            self.assertEqual(approvals[0]["risk_level"], "code")
            self.assertEqual(approvals[0]["sandbox_level"], "subprocess_tempdir_experimental")
            self.assertEqual(approvals[0]["network_isolation"], "best_effort_static_check")


if __name__ == "__main__":
    unittest.main()
