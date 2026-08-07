import json
import unittest

from agent_state import AgentRunState


class AgentRunStateTests(unittest.TestCase):
    def test_starts_in_inspect_and_records_stage_transitions_once(self):
        state = AgentRunState()

        self.assertEqual(state.current_stage, "inspect")
        self.assertEqual(state.record_stage("inspect"), {"stage": "inspect"})
        self.assertEqual(state.record_stage("inspect"), None)
        self.assertEqual(state.record_stage("plan"), {"stage": "plan"})
        self.assertEqual(state.stages, ["inspect", "plan"])

    def test_write_requires_passing_verification_before_report(self):
        state = AgentRunState()

        state.observe_tool_result("write_file", json.dumps({"status": "written", "path": "app.py"}))

        self.assertTrue(state.requires_verification_before_report())
        self.assertEqual(
            state.completion_evidence(),
            {
                "writes_performed": True,
                "verification_observed": False,
                "verification_passed": False,
                "verification_statuses": [],
            },
        )

    def test_restore_requires_passing_verification_before_report(self):
        state = AgentRunState()

        state.observe_tool_result("restore_backup", json.dumps({"status": "restored", "path": "app.py"}))

        self.assertTrue(state.requires_verification_before_report())
        self.assertTrue(state.completion_evidence()["writes_performed"])

    def test_passing_verification_satisfies_completion_evidence(self):
        state = AgentRunState()

        state.observe_tool_result("write_file", json.dumps({"status": "written", "path": "app.py"}))
        state.observe_tool_result("run_verification", json.dumps({"status": "passed", "name": "python-tests"}))

        self.assertFalse(state.requires_verification_before_report())
        self.assertEqual(
            state.completion_evidence(),
            {
                "writes_performed": True,
                "verification_observed": True,
                "verification_passed": True,
                "verification_statuses": ["passed"],
            },
        )

    def test_denied_or_failed_verification_does_not_satisfy_completion(self):
        state = AgentRunState()

        state.observe_tool_result("write_file", json.dumps({"status": "written", "path": "app.py"}))
        state.observe_tool_result("run_verification", json.dumps({"status": "denied", "name": "python-tests"}))
        state.observe_tool_result("run_verification", json.dumps({"status": "failed", "name": "python-tests"}))

        self.assertTrue(state.requires_verification_before_report())
        evidence = state.completion_evidence()
        self.assertTrue(evidence["verification_observed"])
        self.assertFalse(evidence["verification_passed"])
        self.assertEqual(evidence["verification_statuses"], ["denied", "failed"])

    def test_state_snapshot_round_trips_resume_data(self):
        state = AgentRunState()
        state.record_stage("inspect")
        state.record_stage("plan")
        state.observe_tool_result("write_file", json.dumps({"status": "written", "path": "app.py"}))
        state.observe_tool_result("run_verification", json.dumps({"status": "failed", "name": "python-tests"}))

        restored = AgentRunState.from_snapshot(state.to_snapshot())

        self.assertEqual(restored.current_stage, "plan")
        self.assertEqual(restored.stages, ["inspect", "plan"])
        self.assertTrue(restored.requires_verification_before_report())
        self.assertEqual(
            restored.completion_evidence(),
            {
                "writes_performed": True,
                "verification_observed": True,
                "verification_passed": False,
                "verification_statuses": ["failed"],
            },
        )

    def test_invalid_state_snapshot_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid agent state snapshot"):
            AgentRunState.from_snapshot({"current_stage": "", "stages": "inspect"})


if __name__ == "__main__":
    unittest.main()
