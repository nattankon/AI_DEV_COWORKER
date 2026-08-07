import unittest
import sys
import tempfile
import textwrap
from pathlib import Path

from chat_pyodide_sandbox import NodePyodideRuntime, PyodideSandbox, discover_pyodide_runtime


class PyodideSandboxTests(unittest.TestCase):
    def test_missing_runtime_reports_unavailable_without_crashing(self):
        sandbox = PyodideSandbox(runtime_loader=lambda: None)

        result = sandbox.run_python("print(1)")

        self.assertEqual(result["status"], "unavailable")
        self.assertIn("Pyodide", result["error"])
        self.assertEqual(result["sandbox_level"], "pyodide_wasm_unavailable")
        self.assertEqual(result["network_isolation"], "wasm_no_host_network_when_available")

    def test_available_runtime_contract_executes_via_injected_runner(self):
        class FakeRuntime:
            def run_python(self, code):
                return {"stdout": f"ran {code}", "stderr": ""}

        sandbox = PyodideSandbox(runtime_loader=lambda: FakeRuntime())

        result = sandbox.run_python("print(2)")

        self.assertEqual(result["status"], "ok")
        self.assertIn("print(2)", result["stdout"])
        self.assertEqual(result["sandbox_level"], "pyodide_wasm")

    def test_node_pyodide_runtime_invokes_json_runner(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = Path(temp_dir) / "fake_runner.py"
            runner.write_text(
                textwrap.dedent(
                    """
                    import json
                    import sys

                    payload = json.loads(sys.stdin.read())
                    print(json.dumps({"status": "ok", "stdout": "ran " + payload["code"], "stderr": ""}))
                    """
                ).strip(),
                encoding="utf-8",
            )
            runtime = NodePyodideRuntime(runner_path=runner, node_command=sys.executable, timeout_seconds=2)

            result = runtime.run_python("print(3)")

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["stdout"], "ran print(3)")
            self.assertEqual(result["sandbox_level"], "pyodide_wasm")

    def test_node_pyodide_runtime_timeout_is_structured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = Path(temp_dir) / "slow_runner.py"
            runner.write_text(
                "import time\n"
                "time.sleep(2)\n",
                encoding="utf-8",
            )
            runtime = NodePyodideRuntime(runner_path=runner, node_command=sys.executable, timeout_seconds=0.1)

            result = runtime.run_python("print('slow')")

            self.assertEqual(result["status"], "timeout")
            self.assertIn("timed out", result["error"])
            self.assertEqual(result["sandbox_level"], "pyodide_wasm")

    def test_discover_pyodide_runtime_requires_local_package(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = root / "runner.mjs"
            runner.write_text("console.log('{}')", encoding="utf-8")

            missing = discover_pyodide_runtime(app_root=root, runner_path=runner, node_command=sys.executable)
            self.assertIsNone(missing)

            (root / "node_modules" / "pyodide").mkdir(parents=True)
            (root / "node_modules" / "pyodide" / "package.json").write_text("{}", encoding="utf-8")
            found = discover_pyodide_runtime(app_root=root, runner_path=runner, node_command=sys.executable)
            self.assertIsInstance(found, NodePyodideRuntime)

    def test_real_pyodide_runtime_runs_when_package_is_installed(self):
        app_root = Path(__file__).resolve().parents[1]
        if not (app_root / "node_modules" / "pyodide" / "package.json").exists():
            self.skipTest("pyodide npm package is not installed")

        result = PyodideSandbox(app_root=app_root).run_python("print(40 + 2)")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stdout"], "42")
        self.assertEqual(result["sandbox_level"], "pyodide_wasm")


if __name__ == "__main__":
    unittest.main()
