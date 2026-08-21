import unittest

from permission_policy import normalize_permission_mode, should_auto_approve


class PermissionPolicyTests(unittest.TestCase):
    def test_unknown_modes_fall_back_to_manual_control(self):
        self.assertEqual(normalize_permission_mode("manual"), "manual")
        self.assertEqual(normalize_permission_mode("trusted"), "trusted")
        self.assertEqual(normalize_permission_mode("full"), "full")
        self.assertEqual(normalize_permission_mode("unexpected"), "manual")

    def test_manual_control_never_auto_approves_side_effects(self):
        for kind, risk in (
            ("write_file", "write"),
            ("run_verification", "write"),
            ("chat_run_python", "code"),
            ("mcp_tool_call", "destructive"),
        ):
            with self.subTest(kind=kind):
                self.assertFalse(should_auto_approve("manual", kind, {"risk_level": risk}))

    def test_approvals_only_allows_routine_actions_but_prompts_for_high_risk(self):
        self.assertTrue(should_auto_approve("trusted", "write_file", {"risk_level": "write"}))
        self.assertTrue(should_auto_approve("trusted", "run_verification", {"risk_level": "write"}))
        self.assertFalse(should_auto_approve("trusted", "mcp_tool_call", {"risk_level": "write"}))
        self.assertFalse(should_auto_approve("trusted", "restore_backup", {"risk_level": "destructive"}))
        self.assertFalse(should_auto_approve("trusted", "chat_run_python", {"risk_level": "code"}))
        self.assertFalse(should_auto_approve("trusted", "unknown_action", {"risk_level": "write"}))

    def test_full_access_auto_approves_known_actions_but_not_unknown_kinds(self):
        for kind in ("write_file", "run_verification", "restore_backup", "chat_run_python", "mcp_tool_call"):
            with self.subTest(kind=kind):
                self.assertTrue(should_auto_approve("full", kind, {"risk_level": "destructive"}))
        self.assertFalse(should_auto_approve("full", "unknown_action", {"risk_level": "write"}))


if __name__ == "__main__":
    unittest.main()
