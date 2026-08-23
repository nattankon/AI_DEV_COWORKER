from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from ipc_sidecar import IpcDependencies, IpcSidecar


class FakeWorkspaceTools:
    schemas = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "read",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    ]

    def dispatch(self, name, arguments):
        return json.dumps({"status": "ok", "name": name})


class FakeTunnelController:
    def __init__(self, *, on_state, **_kwargs):
        self.on_state = on_state
        self.starts = []
        self.stops = []
        self.state = {"status": "off", "provider": "", "grant_id": "", "grant_revision": 0, "workspace_path": ""}

    def start(self, **kwargs):
        self.starts.append(kwargs)
        gateway = kwargs["gateway"]
        self.state = {
            "status": "connected",
            "provider": kwargs["provider"],
            "grant_id": gateway.grant_id,
            "grant_revision": gateway.grant_revision,
            "workspace_path": str(gateway.workspace),
            "endpoint": "https://phase4.example.test/mcp",
            "auth_required": True,
            "expires_at": "2026-08-21T23:00:00+00:00",
            "tool_count": 1,
            "error": "",
        }
        self.on_state(self.state)
        return self.state

    def stop(self, reason="manual"):
        self.stops.append(reason)
        self.state = {"status": "off", "provider": "", "grant_id": "", "grant_revision": 0, "workspace_path": ""}
        self.on_state(self.state)
        return self.state

    def public_state(self):
        return dict(self.state)


def events(output):
    return [json.loads(line) for line in output.getvalue().splitlines() if line.strip()]


class IpcWebChatTunnelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = io.StringIO()
        self.controllers = []

        def factory(**kwargs):
            controller = FakeTunnelController(**kwargs)
            self.controllers.append(controller)
            return controller

        self.sidecar = IpcSidecar(IpcDependencies(
            workspace=Path(self.temp.name),
            output=self.output,
            input_stream=io.StringIO(),
            workspace_tools_factory=lambda _root: FakeWorkspaceTools(),
            web_chat_tunnel_controller_factory=factory,
            web_chat_gateway_audit_sink=lambda *_args: None,
        ))

    def tearDown(self):
        self.sidecar.close()
        self.temp.cleanup()

    def send(self, command, **payload):
        self.sidecar.handle_line(json.dumps({"command": command, **payload}))

    def bind(self, grant_id="grant-1", revision=3):
        self.send(
            "web_chat_gateway_bind",
            workspace_path=self.temp.name,
            grant_id=grant_id,
            grant_revision=revision,
            permission_mode="manual",
        )

    def test_start_emits_redacted_connected_state(self):
        self.bind()
        self.send(
            "web_chat_tunnel_start",
            provider="test",
            credential="super-secret",
            expires_at=2_000_000_000,
            idle_timeout_seconds=60,
            grant_id="grant-1",
            grant_revision=3,
        )
        self.sidecar.wait_for_idle()
        states = [event for event in events(self.output) if event["__ipc_type"] == "web_chat_tunnel_state"]
        self.assertEqual(states[-1]["status"], "connected")
        self.assertNotIn("super-secret", self.output.getvalue())
        self.assertEqual(len(self.controllers[0].starts), 1)

    def test_openai_options_reach_controller_but_never_public_events(self):
        self.bind()
        self.send(
            "web_chat_tunnel_start",
            provider="openai",
            credential="local-secret",
            expires_at=2_000_000_000,
            grant_id="grant-1",
            grant_revision=3,
            provider_options={
                "tunnel_id": "tunnel_0123456789abcdef0123456789abcdef",
                "runtime_api_key": "sk-runtime-secret",
            },
        )
        self.sidecar.wait_for_idle()
        start = self.controllers[0].starts[0]
        self.assertEqual(start["provider_options"]["tunnel_id"], "tunnel_0123456789abcdef0123456789abcdef")
        self.assertEqual(start["provider_options"]["runtime_api_key"], "sk-runtime-secret")
        self.assertNotIn("sk-runtime-secret", self.output.getvalue())
        self.assertNotIn("local-secret", self.output.getvalue())

    def test_stale_or_missing_gateway_start_fails_closed(self):
        self.send("web_chat_tunnel_start", provider="test", credential="secret", expires_at=2_000_000_000, grant_id="missing", grant_revision=1)
        self.sidecar.wait_for_idle()
        states = [event for event in events(self.output) if event["__ipc_type"] == "web_chat_tunnel_state"]
        self.assertEqual(states[-1]["status"], "error")
        self.assertIn("gateway", states[-1]["error"].casefold())

    def test_replacing_or_unbinding_gateway_stops_tunnel_first(self):
        self.bind()
        self.send("web_chat_tunnel_start", provider="test", credential="secret", expires_at=2_000_000_000, grant_id="grant-1", grant_revision=3)
        self.sidecar.wait_for_idle()
        controller = self.controllers[0]
        self.bind(grant_id="grant-2", revision=4)
        self.assertIn("grant-replaced", controller.stops)
        self.send("web_chat_gateway_unbind", reason="revoked")
        self.assertIn("revoked", controller.stops)

    def test_close_stops_tunnel(self):
        self.bind()
        self.send("web_chat_tunnel_start", provider="test", credential="secret", expires_at=2_000_000_000, grant_id="grant-1", grant_revision=3)
        self.sidecar.wait_for_idle()
        controller = self.controllers[0]
        self.sidecar.close()
        self.assertIn("sidecar-closed", controller.stops)


if __name__ == "__main__":
    unittest.main()
