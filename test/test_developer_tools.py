from pathlib import Path
import shutil
import subprocess
import sys
import time
import tempfile
import unittest

import json

from developer_tools import (
    CommandProposal,
    DeveloperTools,
    VerificationCommand,
    load_project_verification_commands,
)


class DeveloperToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _git(self, *arguments: str) -> None:
        subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )

    def _initialize_repository(self) -> None:
        self._git("init")
        self._git("config", "user.email", "cowork@example.invalid")
        self._git("config", "user.name", "Cowork Test")
        (self.root / "app.py").write_text("print('before')\n", encoding="utf-8")
        (self.root / ".env").write_text("TOKEN=before\n", encoding="utf-8")
        self._git("add", "app.py", ".env")
        self._git("commit", "-m", "baseline")

    def _write_project_presets(self, presets: dict) -> None:
        config_dir = self.root / ".cowork"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "verify.json").write_text(json.dumps({"presets": presets}), encoding="utf-8")

    def test_project_presets_extend_the_allowlist_and_run(self):
        self._write_project_presets({
            "smoke": {"argv": [sys.executable, "-c", "print('ok')"], "timeout_seconds": 30},
        })
        tools = DeveloperTools(self.root, approve_command=lambda proposal: True)

        # The project preset joins the default allowlist and is runnable.
        self.assertIn("smoke", tools.verification_names)
        self.assertIn("python-tests", tools.verification_names)
        result = tools.run_verification("smoke")
        self.assertEqual(result["status"], "passed")
        self.assertIn("ok", result.get("stdout", ""))

    def test_malformed_project_presets_are_ignored(self):
        self._write_project_presets({
            "": {"argv": ["echo", "x"]},
            "bad_argv": {"argv": "not-a-list"},
            "empty_argv": {"argv": []},
            "good": {"argv": [sys.executable, "-c", "print(1)"]},
        })
        commands = load_project_verification_commands(self.root)
        self.assertEqual(set(commands), {"good"})

    def test_missing_project_config_is_a_no_op(self):
        self.assertEqual(load_project_verification_commands(self.root), {})

    def test_git_status_and_diff_report_changes_without_secret_paths(self):
        self._initialize_repository()
        (self.root / "app.py").write_text("print('after')\n", encoding="utf-8")
        (self.root / ".env").write_text("TOKEN=never-expose-this\n", encoding="utf-8")
        tools = DeveloperTools(self.root, approve_command=lambda proposal: True)

        status = tools.git_status()
        diff = tools.git_diff()

        self.assertEqual(status["status"], "ok")
        self.assertIn("app.py", status["changed_files"])
        self.assertNotIn(".env", str(status))
        self.assertEqual(diff["status"], "ok")
        self.assertIn("app.py", diff["changed_files"])
        self.assertIn("print('after')", diff["stdout"])
        self.assertNotIn(".env", str(diff))
        self.assertNotIn("never-expose-this", str(diff))

    def test_git_tools_return_unavailable_outside_a_repository(self):
        tools = DeveloperTools(self.root, approve_command=lambda proposal: True)

        status = tools.git_status()
        diff = tools.git_diff()

        self.assertEqual(status["status"], "unavailable")
        self.assertEqual(diff["status"], "unavailable")
        self.assertIn("not a Git repository", status["error"])

    def test_verification_runs_only_named_approved_command(self):
        proposals: list[CommandProposal] = []
        events = []
        commands = {
            "python-tests": VerificationCommand(
                name="python-tests",
                argv=(sys.executable, "-c", "print('verification-ok')"),
                timeout_seconds=5,
            )
        }
        tools = DeveloperTools(
            self.root,
            approve_command=lambda proposal: proposals.append(proposal) or True,
            verification_commands=commands,
            audit_sink=lambda event_type, payload: events.append((event_type, payload)),
        )

        result = tools.run_verification("python-tests")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["stdout"].strip(), "verification-ok")
        self.assertEqual(proposals[0].name, "python-tests")
        self.assertEqual(proposals[0].argv, commands["python-tests"].argv)
        self.assertEqual(
            [event_type for event_type, _payload in events],
            [
                "verification_approval_requested",
                "verification_approval_decision",
                "verification_started",
                "verification_finished",
            ],
        )
        self.assertEqual(events[0][1]["name"], "python-tests")
        self.assertEqual(events[0][1]["argv"], list(commands["python-tests"].argv))
        self.assertTrue(events[1][1]["approved"])
        self.assertEqual(events[3][1]["status"], "passed")
        self.assertEqual(events[3][1]["exit_code"], 0)
        self.assertIn("duration_ms", events[3][1])

    def test_denied_and_unknown_verification_never_start_a_process(self):
        marker = self.root / "started.txt"
        events = []
        command = VerificationCommand(
            name="python-tests",
            argv=(sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('yes')"),
            timeout_seconds=5,
        )
        tools = DeveloperTools(
            self.root,
            approve_command=lambda proposal: False,
            verification_commands={"python-tests": command},
            audit_sink=lambda event_type, payload: events.append((event_type, payload)),
        )

        denied = tools.run_verification("python-tests")
        unknown = tools.run_verification("rm-everything")

        self.assertEqual(denied["status"], "denied")
        self.assertEqual(unknown["status"], "error")
        self.assertIn("not allowlisted", unknown["error"])
        self.assertFalse(marker.exists())
        self.assertEqual(
            [event_type for event_type, _payload in events],
            [
                "verification_approval_requested",
                "verification_approval_decision",
                "verification_rejected",
            ],
        )
        self.assertFalse(events[1][1]["approved"])
        self.assertEqual(events[2][1]["reason"], "not_allowlisted")

    def test_verification_timeout_and_output_limit_are_structured(self):
        killed_pids = []
        events = []
        commands = {
            "slow": VerificationCommand(
                name="slow",
                argv=(sys.executable, "-c", "import time; time.sleep(2)"),
                timeout_seconds=0.05,
            ),
            "loud": VerificationCommand(
                name="loud",
                argv=(sys.executable, "-c", "print('x' * 500)"),
                timeout_seconds=5,
            ),
        }
        tools = DeveloperTools(
            self.root,
            approve_command=lambda proposal: True,
            verification_commands=commands,
            max_output_chars=80,
            process_tree_killer=lambda pid: killed_pids.append(pid),
            audit_sink=lambda event_type, payload: events.append((event_type, payload)),
        )

        timed_out = tools.run_verification("slow")
        truncated = tools.run_verification("loud")

        self.assertEqual(timed_out["status"], "timeout")
        self.assertTrue(timed_out["process_tree_terminated"])
        self.assertEqual(len(killed_pids), 1)
        self.assertEqual(truncated["status"], "passed")
        self.assertTrue(truncated["truncated"])
        self.assertLessEqual(len(truncated["stdout"]), 80)
        timeout_events = [payload for event_type, payload in events if event_type == "verification_timeout"]
        self.assertEqual(timeout_events[0]["name"], "slow")
        self.assertTrue(timeout_events[0]["process_tree_terminated"])

    def test_timeout_cleans_up_real_child_process_tree(self):
        heartbeat = self.root / "child-heartbeat.txt"
        child_script = (
            "from pathlib import Path\n"
            "import sys, time\n"
            f"heartbeat = Path({str(heartbeat)!r})\n"
            "while True:\n"
            "    heartbeat.write_text(str(time.time()), encoding='utf-8')\n"
            "    time.sleep(0.05)\n"
        )
        parent_script = (
            "import subprocess, sys, time\n"
            f"subprocess.Popen([sys.executable, '-c', {child_script!r}])\n"
            "time.sleep(30)\n"
        )
        tools = DeveloperTools(
            self.root,
            approve_command=lambda proposal: True,
            verification_commands={
                "worker-tree": VerificationCommand(
                    name="worker-tree",
                    argv=(sys.executable, "-c", parent_script),
                    timeout_seconds=0.4,
                )
            },
        )

        result = tools.run_verification("worker-tree")
        before = heartbeat.read_text(encoding="utf-8") if heartbeat.exists() else ""
        time.sleep(0.35)
        after = heartbeat.read_text(encoding="utf-8") if heartbeat.exists() else ""

        self.assertEqual(result["status"], "timeout")
        self.assertTrue(result["process_tree_terminated"])
        self.assertTrue(heartbeat.exists())
        self.assertEqual(after, before)

    def test_timeout_cleans_up_real_npm_worker_tree(self):
        npm = shutil.which("npm.cmd" if sys.platform.startswith("win") else "npm")
        if npm is None:
            self.skipTest("npm is not available")
        heartbeat = self.root / "npm-heartbeat.txt"
        (self.root / "package.json").write_text(
            '{"scripts":{"worker-tree":"node parent.mjs"}}\n',
            encoding="utf-8",
        )
        (self.root / "child.mjs").write_text(
            "import fs from 'node:fs';\n"
            f"const heartbeat = {str(heartbeat)!r};\n"
            "setInterval(() => fs.writeFileSync(heartbeat, String(Date.now())), 50);\n",
            encoding="utf-8",
        )
        (self.root / "parent.mjs").write_text(
            "import { spawn } from 'node:child_process';\n"
            "spawn(process.execPath, ['child.mjs'], { stdio: 'ignore' });\n"
            "setTimeout(() => {}, 30000);\n",
            encoding="utf-8",
        )
        tools = DeveloperTools(
            self.root,
            approve_command=lambda proposal: True,
            verification_commands={
                "npm-worker-tree": VerificationCommand(
                    name="npm-worker-tree",
                    argv=(npm, "run", "worker-tree"),
                    timeout_seconds=2.0,
                )
            },
        )

        result = tools.run_verification("npm-worker-tree")
        before = heartbeat.read_text(encoding="utf-8") if heartbeat.exists() else ""
        time.sleep(0.35)
        after = heartbeat.read_text(encoding="utf-8") if heartbeat.exists() else ""

        self.assertEqual(result["status"], "timeout")
        self.assertTrue(result["process_tree_terminated"])
        self.assertTrue(heartbeat.exists())
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
