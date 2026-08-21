from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from web_chat_mcp_gateway import WebChatLocalMcpGateway


class _FakeProvider:
    def __init__(self):
        self.schemas = [
            {
                "type": "function",
                "function": {
                    "name": "trusted_read",
                    "description": "Read trusted metadata.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                    "annotations": {"readOnlyHint": True, "workspaceBoundHint": True},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "invalid_result",
                    "description": "Returns an invalid provider result.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                    "annotations": {"readOnlyHint": True, "workspaceBoundHint": True},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "missing_annotation",
                    "description": "Must fail closed.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_tool",
                    "description": "Must not be exposed in Phase 3.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                    "annotations": {"readOnlyHint": False, "workspaceBoundHint": True},
                },
            },
        ]
        self.calls = []

    def dispatch(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        if name == "invalid_result":
            return "not-json"
        return json.dumps({"status": "ok", "provider": name})


class WebChatLocalMcpGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "notes.txt").write_text("hello gateway", encoding="utf-8")
        (self.root / ".env").write_text("TOKEN=hidden", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def gateway(self, **kwargs):
        return WebChatLocalMcpGateway(
            workspace=self.root,
            grant_id="grant-1",
            grant_revision=7,
            permission_mode="manual",
            audit_sink=lambda _event, _payload: None,
            **kwargs,
        )

    def test_catalog_exposes_only_explicit_read_only_workspace_tools(self):
        gateway = self.gateway()

        catalog = gateway.list_tools()
        names = [tool["name"] for tool in catalog]

        self.assertEqual(
            names,
            [
                "list_directory",
                "search_files",
                "read_file",
                "write_file",
                "edit_file",
                "list_backups",
                "restore_backup",
                "git_status",
                "git_diff",
                "run_verification",
            ],
        )
        read_only = {tool["name"] for tool in catalog if tool["annotations"]["readOnlyHint"] is True}
        self.assertEqual(read_only, {"list_directory", "search_files", "read_file", "list_backups", "git_status", "git_diff"})
        self.assertTrue(all(tool["annotations"]["workspaceBoundHint"] is True for tool in catalog))
        self.assertTrue(next(tool for tool in catalog if tool["name"] == "restore_backup")["annotations"]["destructiveHint"])

    def test_dispatch_reuses_workspace_containment_and_secret_guard(self):
        gateway = self.gateway()

        read = json.loads(gateway.dispatch("read_file", {"path": "notes.txt"}, grant_id="grant-1", grant_revision=7))
        escaped = json.loads(gateway.dispatch("read_file", {"path": "../outside.txt"}, grant_id="grant-1", grant_revision=7))
        secret = json.loads(gateway.dispatch("read_file", {"path": ".env"}, grant_id="grant-1", grant_revision=7))

        self.assertEqual(read, {"status": "ok", "content": "hello gateway"})
        self.assertEqual(escaped["status"], "error")
        self.assertEqual(secret["status"], "denied")

    def test_stale_or_unknown_calls_fail_closed(self):
        gateway = self.gateway()

        stale = json.loads(gateway.dispatch("read_file", {"path": "notes.txt"}, grant_id="old", grant_revision=6))
        malformed = json.loads(gateway.dispatch("read_file", {"path": "notes.txt"}, grant_id="grant-1", grant_revision="bad"))
        unknown = json.loads(gateway.dispatch("write_file", {"path": "x", "content": "x"}, grant_id="grant-1", grant_revision=7))

        self.assertEqual(stale["status"], "denied")
        self.assertIn("stale", stale["error"].lower())
        self.assertEqual(malformed["status"], "denied")
        self.assertEqual(unknown["status"], "denied")

    def test_side_effect_requires_current_tunnel_generation_and_carries_full_context(self):
        approvals = []
        gateway = self.gateway(approval_callback=lambda kind, question, proposal, context: approvals.append(
            (kind, question, proposal, context)
        ) or True)
        gateway.activate_tunnel(12)

        stale = json.loads(gateway.dispatch(
            "write_file",
            {"path": "created.txt", "content": "complete remote content"},
            grant_id="grant-1",
            grant_revision=7,
            tunnel_generation=11,
        ))
        written = json.loads(gateway.dispatch(
            "write_file",
            {"path": "created.txt", "content": "complete remote content"},
            grant_id="grant-1",
            grant_revision=7,
            tunnel_generation=12,
        ))

        self.assertEqual(stale["status"], "denied")
        self.assertEqual(written["status"], "written")
        self.assertEqual((self.root / "created.txt").read_text(encoding="utf-8"), "complete remote content")
        self.assertEqual(len(approvals), 1)
        kind, _question, proposal, context = approvals[0]
        self.assertEqual(kind, "write_file")
        self.assertIn("+complete remote content", proposal["diff"])
        self.assertEqual(context["arguments"], {"path": "created.txt", "content": "complete remote content"})
        self.assertEqual(context["grant_id"], "grant-1")
        self.assertEqual(context["grant_revision"], 7)
        self.assertEqual(context["tunnel_generation"], 12)

    def test_tunnel_deactivation_denies_future_side_effects(self):
        gateway = self.gateway(approval_callback=lambda *_args: True)
        gateway.activate_tunnel(4)
        gateway.deactivate_tunnel(4, "disconnected")

        result = json.loads(gateway.dispatch(
            "write_file",
            {"path": "blocked.txt", "content": "no"},
            grant_id="grant-1",
            grant_revision=7,
            tunnel_generation=4,
        ))

        self.assertEqual(result["status"], "denied")
        self.assertFalse((self.root / "blocked.txt").exists())

    def test_tunnel_deactivation_during_approval_denies_the_side_effect(self):
        gateway = None

        def approve_then_disconnect(*_args):
            gateway.deactivate_tunnel(9, "disconnected-during-approval")
            return True

        gateway = self.gateway(approval_callback=approve_then_disconnect)
        gateway.activate_tunnel(9)

        result = json.loads(gateway.dispatch(
            "write_file",
            {"path": "race.txt", "content": "must not be written"},
            grant_id="grant-1",
            grant_revision=7,
            tunnel_generation=9,
        ))

        self.assertEqual(result["status"], "denied")
        self.assertFalse((self.root / "race.txt").exists())

    def test_provider_side_effect_rechecks_tunnel_after_approval(self):
        provider = _FakeProvider()
        gateway = None

        def approve_then_disconnect(*_args):
            gateway.deactivate_tunnel(10, "disconnected-during-approval")
            return True

        gateway = self.gateway(providers={"mcp": provider}, approval_callback=approve_then_disconnect)
        gateway.activate_tunnel(10)

        result = json.loads(gateway.dispatch(
            "mcp__write_tool",
            {},
            grant_id="grant-1",
            grant_revision=7,
            tunnel_generation=10,
        ))

        self.assertEqual(result["status"], "denied")
        self.assertEqual(provider.calls, [])

    def test_edit_and_restore_keep_workspace_diff_and_destructive_approval_kinds(self):
        (self.root / "notes.txt").write_text("before\n", encoding="utf-8")
        backup = self.root / ".cowork" / "backups" / "20260822T010203000000Z" / "notes.txt"
        backup.parent.mkdir(parents=True)
        backup.write_text("restored\n", encoding="utf-8")
        approvals = []
        gateway = self.gateway(approval_callback=lambda kind, _question, proposal, context: approvals.append(
            (kind, proposal, context)
        ) or False)
        gateway.activate_tunnel(6)

        edited = json.loads(gateway.dispatch(
            "edit_file",
            {"path": "notes.txt", "old_string": "before", "new_string": "after"},
            grant_id="grant-1",
            grant_revision=7,
            tunnel_generation=6,
        ))
        restored = json.loads(gateway.dispatch(
            "restore_backup",
            {"backup_path": ".cowork/backups/20260822T010203000000Z/notes.txt"},
            grant_id="grant-1",
            grant_revision=7,
            tunnel_generation=6,
        ))

        self.assertEqual(edited["status"], "denied")
        self.assertEqual(restored["status"], "denied")
        self.assertEqual((self.root / "notes.txt").read_text(encoding="utf-8"), "before\n")
        self.assertEqual([item[0] for item in approvals], ["write_file", "restore_backup"])
        self.assertEqual(approvals[0][2]["arguments"]["new_string"], "after")
        self.assertIn("+restored", approvals[1][1]["diff"])

    def test_optional_provider_requires_workspace_binding_and_approval_for_writes(self):
        provider = _FakeProvider()
        gateway = self.gateway(providers={"mcp": provider})

        names = [tool["name"] for tool in gateway.list_tools()]
        result = json.loads(gateway.dispatch("mcp__trusted_read", {}, grant_id="grant-1", grant_revision=7))

        self.assertIn("mcp__trusted_read", names)
        self.assertNotIn("mcp__missing_annotation", names)
        self.assertIn("mcp__write_tool", names)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(provider.calls, [("trusted_read", {})])

        gateway.activate_tunnel(3)
        denied_write = json.loads(gateway.dispatch(
            "mcp__write_tool", {}, grant_id="grant-1", grant_revision=7, tunnel_generation=3
        ))
        self.assertEqual(denied_write["status"], "denied")
        self.assertEqual(provider.calls, [("trusted_read", {})])

        invalid = json.loads(gateway.dispatch("mcp__invalid_result", {}, grant_id="grant-1", grant_revision=7))
        self.assertEqual(invalid["status"], "error")


if __name__ == "__main__":
    unittest.main()
