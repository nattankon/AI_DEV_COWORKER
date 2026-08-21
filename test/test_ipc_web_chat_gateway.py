from __future__ import annotations

import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from ipc_sidecar import IpcDependencies, IpcSidecar


class IpcWebChatGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "README.md").write_text("gateway", encoding="utf-8")
        self.output = io.StringIO()
        self.sidecar = IpcSidecar(
            IpcDependencies(
                workspace=self.root,
                app_root=self.root,
                output=self.output,
                input_stream=io.StringIO(),
                web_chat_gateway_audit_sink=lambda _event, _payload: None,
            )
        )

    def tearDown(self):
        self.temp.cleanup()

    def events(self):
        return [json.loads(line) for line in self.output.getvalue().splitlines() if line.strip()]

    def test_bind_and_unbind_emit_public_gateway_state(self):
        self.sidecar.handle_line(json.dumps({
            "command": "web_chat_gateway_bind",
            "workspace_path": str(self.root),
            "grant_id": "grant-7",
            "grant_revision": 7,
            "permission_mode": "manual",
        }))

        bound = self.events()[-1]
        self.assertEqual(bound["__ipc_type"], "web_chat_gateway_state")
        self.assertEqual(bound["status"], "ready")
        self.assertEqual(bound["grant_id"], "grant-7")
        self.assertEqual(bound["tool_count"], 10)
        self.assertTrue(bound["tools_enabled"])
        self.assertFalse(bound["tunnel_connected"])

        self.sidecar.handle_line(json.dumps({"command": "web_chat_gateway_unbind", "reason": "revoked"}))
        unbound = self.events()[-1]
        self.assertEqual(unbound["status"], "off")
        self.assertFalse(unbound["tools_enabled"])
        self.assertEqual(unbound["tools"], [])

    def test_invalid_bind_fails_closed_without_replacing_active_gateway(self):
        self.sidecar.handle_line(json.dumps({
            "command": "web_chat_gateway_bind",
            "workspace_path": str(self.root),
            "grant_id": "grant-7",
            "grant_revision": 7,
            "permission_mode": "manual",
        }))
        self.sidecar.handle_line(json.dumps({
            "command": "web_chat_gateway_bind",
            "workspace_path": str(self.root / "missing"),
            "grant_id": "grant-8",
            "grant_revision": 8,
            "permission_mode": "manual",
        }))
        self.sidecar.handle_line(json.dumps({"command": "web_chat_gateway_state"}))

        events = self.events()
        self.assertEqual(events[-2]["__ipc_type"], "backend-log")
        self.assertIn("missing", events[-2]["message"].lower())
        self.assertEqual(events[-1]["grant_id"], "grant-7")
        self.assertEqual(events[-1]["status"], "ready")

    def test_internal_call_seam_dispatches_only_for_current_grant(self):
        self.sidecar.handle_line(json.dumps({
            "command": "web_chat_gateway_bind",
            "workspace_path": str(self.root),
            "grant_id": "grant-7",
            "grant_revision": 7,
            "permission_mode": "manual",
        }))
        self.sidecar.handle_line(json.dumps({
            "command": "web_chat_gateway_call",
            "request_id": "request-1",
            "grant_id": "grant-7",
            "grant_revision": 7,
            "tool": "read_file",
            "arguments": {"path": "README.md"},
        }))
        self.sidecar.handle_line(json.dumps({
            "command": "web_chat_gateway_call",
            "request_id": "request-2",
            "grant_id": "stale",
            "grant_revision": 6,
            "tool": "read_file",
            "arguments": {"path": "README.md"},
        }))

        success, stale = self.events()[-2:]
        self.assertEqual(success["__ipc_type"], "web_chat_gateway_tool_result")
        self.assertEqual(success["request_id"], "request-1")
        self.assertEqual(success["result"], {"status": "ok", "content": "gateway"})
        self.assertEqual(stale["result"]["status"], "denied")

    def test_web_chat_write_uses_existing_approval_event_and_full_remote_arguments(self):
        self.sidecar.handle_line(json.dumps({
            "command": "web_chat_gateway_bind",
            "workspace_path": str(self.root),
            "grant_id": "grant-7",
            "grant_revision": 7,
            "permission_mode": "manual",
        }))
        self.sidecar._web_chat_gateway.activate_tunnel(9)
        results = []
        worker = threading.Thread(target=lambda: results.append(json.loads(self.sidecar._web_chat_gateway.dispatch(
            "write_file",
            {"path": "remote.txt", "content": "from ChatGPT"},
            grant_id="grant-7",
            grant_revision=7,
            tunnel_generation=9,
        ))))
        worker.start()
        deadline = time.time() + 1
        approval = None
        while time.time() < deadline and approval is None:
            approval = next((event for event in reversed(self.events()) if event.get("__ipc_type") == "cowork_interactive_question"), None)
            time.sleep(0.01)
        self.assertIsNotNone(approval)
        self.assertEqual(approval["proposal"]["origin"], "web_chat")
        self.assertEqual(approval["proposal"]["full_payload"]["arguments"]["content"], "from ChatGPT")
        self.assertEqual(approval["proposal"]["full_payload"]["tunnel_generation"], 9)

        self.sidecar.handle_line(json.dumps({
            "command": "answer_question",
            "approval_id": approval["approval_id"],
            "answer": "allow",
        }))
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0]["status"], "written")
        self.assertEqual((self.root / "remote.txt").read_text(encoding="utf-8"), "from ChatGPT")

    def test_deactivating_tunnel_cancels_pending_web_chat_approval(self):
        self.sidecar.handle_line(json.dumps({
            "command": "web_chat_gateway_bind",
            "workspace_path": str(self.root),
            "grant_id": "grant-7",
            "grant_revision": 7,
            "permission_mode": "manual",
        }))
        gateway = self.sidecar._web_chat_gateway
        gateway.activate_tunnel(10)
        results = []
        worker = threading.Thread(target=lambda: results.append(json.loads(gateway.dispatch(
            "write_file",
            {"path": "cancelled.txt", "content": "blocked"},
            grant_id="grant-7",
            grant_revision=7,
            tunnel_generation=10,
        ))))
        worker.start()
        deadline = time.time() + 1
        while time.time() < deadline and not self.sidecar._pending_approvals:
            time.sleep(0.01)
        self.assertTrue(self.sidecar._pending_approvals)

        gateway.deactivate_tunnel(10, "manual")
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0]["status"], "denied")
        self.assertFalse((self.root / "cancelled.txt").exists())

    def test_trusted_web_chat_profile_reuses_native_auto_approval_policy(self):
        self.sidecar.handle_line(json.dumps({
            "command": "web_chat_gateway_bind",
            "workspace_path": str(self.root),
            "grant_id": "grant-trusted",
            "grant_revision": 4,
            "permission_mode": "trusted",
        }))
        gateway = self.sidecar._web_chat_gateway
        gateway.activate_tunnel(3)

        result = json.loads(gateway.dispatch(
            "write_file",
            {"path": "trusted.txt", "content": "approved by shared policy"},
            grant_id="grant-trusted",
            grant_revision=4,
            tunnel_generation=3,
        ))

        self.assertEqual(result["status"], "written")
        self.assertEqual((self.root / "trusted.txt").read_text(encoding="utf-8"), "approved by shared policy")
        self.assertFalse(any(event.get("__ipc_type") == "cowork_interactive_question" for event in self.events()))


if __name__ == "__main__":
    unittest.main()
