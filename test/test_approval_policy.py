import unittest

from approval_policy import build_approval_payload


class ApprovalPolicyTests(unittest.TestCase):
    def test_code_execution_payload_is_informed_and_fail_closed(self):
        payload = build_approval_payload(
            "chat_run_python",
            "Approve running Chat Python code?",
            {
                "tool": "run_python",
                "code": "print('short')",
                "full_code": "print('short')",
                "sandbox_level": "subprocess_tempdir_experimental",
                "network_isolation": "best_effort_static_check",
            },
        )

        self.assertEqual(payload["risk_level"], "code")
        self.assertEqual(payload["default_decision"], "deny")
        self.assertIn("experimental", payload["risk_summary"].casefold())
        self.assertEqual(payload["details"]["sandbox_level"], "subprocess_tempdir_experimental")
        self.assertEqual(payload["full_payload"]["full_code"], "print('short')")
        self.assertIn("once", payload["allow_scopes"])

    def test_mcp_write_payload_is_side_effecting(self):
        payload = build_approval_payload(
            "mcp_tool_call",
            "Approve MCP tool calendar/write_event?",
            {"server": "calendar", "tool": "write_event", "arguments": {"title": "demo"}},
        )

        self.assertEqual(payload["risk_level"], "write")
        self.assertIn("calendar", payload["subject"])
        self.assertEqual(payload["details"]["tool"], "write_event")

    def test_verification_payload_is_write_like_and_diff_payload_is_write(self):
        verification = build_approval_payload("run_verification", "Approve tests?", {"name": "frontend-tests"})
        file_write = build_approval_payload("write_file", "Approve write?", {"relative_path": "README.md", "diff": "+x"})
        restore = build_approval_payload("restore_backup", "Approve restore?", {"relative_path": "README.md"})

        self.assertEqual(verification["risk_level"], "write")
        self.assertEqual(file_write["risk_level"], "write")
        self.assertEqual(restore["risk_level"], "destructive")


if __name__ == "__main__":
    unittest.main()
