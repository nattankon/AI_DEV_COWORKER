from pathlib import Path
import tempfile
import unittest

from agent_config import build_cowork_system_prompt, load_cowork_memory_context


class AgentConfigTests(unittest.TestCase):
    def test_loading_memory_does_not_create_files_without_approval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context = load_cowork_memory_context("", temp_dir, {"output_dir": temp_dir})

            self.assertEqual(context.existing_memory, "")
            self.assertFalse((root / ".claude" / "cowork_memory.local.md").exists())

    def test_prompt_routes_memory_creation_through_write_tool(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            context = load_cowork_memory_context("", temp_dir, {"output_dir": temp_dir})

        prompt = build_cowork_system_prompt(context)
        self.assertIn("If the memory file does not exist", prompt)
        self.assertIn("write_file", prompt)
        self.assertIn("Secret files and credential stores are blocked", prompt)
        self.assertIn("git_status", prompt)
        self.assertIn("git_diff", prompt)
        self.assertIn("run_verification", prompt)
        self.assertIn("Inspect -> Plan -> Act -> Verify -> Report", prompt)
        self.assertIn("Do not report implementation success after file writes until run_verification passes", prompt)


if __name__ == "__main__":
    unittest.main()
