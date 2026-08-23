from __future__ import annotations

import io
import json
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from web_chat_tunnel import CloudflaredQuickTunnelAdapter, WebChatTunnelController


class FakeGateway:
    grant_id = "grant-1"
    grant_revision = 7
    permission_mode = "manual"
    workspace = "C:/Work/A"

    def __init__(self):
        self.calls = []
        self.activated = []
        self.deactivated = []

    def list_tools(self):
        return [{
            "name": "read_file",
            "description": "Read a workspace file",
            "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}},
            "annotations": {"readOnlyHint": True},
        }]

    def activate_tunnel(self, generation):
        self.activated.append(generation)

    def deactivate_tunnel(self, generation, reason):
        self.deactivated.append((generation, reason))

    def dispatch(self, tool_name, arguments, *, grant_id, grant_revision, tunnel_generation=None):
        self.calls.append((tool_name, arguments, grant_id, grant_revision, tunnel_generation))
        return json.dumps({"status": "ok", "content": "hello"})


class FakeAdapter:
    def __init__(self):
        self.local_endpoint = ""
        self.stopped = False

    def start(self, local_endpoint):
        self.local_endpoint = local_endpoint
        return "https://phase4.example.test/mcp"

    def health(self):
        return not self.stopped

    def stop(self):
        self.stopped = True


class BlockingAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def start(self, local_endpoint):
        self.local_endpoint = local_endpoint
        self.entered.set()
        self.release.wait(timeout=2)
        return "https://late.example.test/mcp"


class FakeProcess:
    def __init__(self, stderr_text):
        self.stderr = io.StringIO(stderr_text)
        self.pid = 1234
        self.terminated = False

    def poll(self):
        return 0 if self.terminated else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.terminated = True
        return 0

    def kill(self):
        self.terminated = True


def post_json(endpoint, payload, token="secret-token"):
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urlopen(request, timeout=2) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


class WebChatTunnelControllerTests(unittest.TestCase):
    def setUp(self):
        self.adapter = FakeAdapter()
        self.controller = WebChatTunnelController(
            adapter_factories={"test": lambda: self.adapter},
            audit_sink=lambda *_args: None,
        )
        self.gateway = FakeGateway()

    def tearDown(self):
        self.controller.stop("test-cleanup")

    def start(self, *, idle_timeout=30):
        return self.controller.start(
            gateway=self.gateway,
            provider="test",
            credential="secret-token",
            expires_at=time.time() + 60,
            idle_timeout_seconds=idle_timeout,
        )

    def test_requires_bearer_auth_and_never_exposes_the_credential(self):
        state = self.start()
        self.assertEqual(state["status"], "connected")
        self.assertNotIn("secret-token", json.dumps(state))
        self.assertNotIn("credential", state)
        request = Request(
            self.adapter.local_endpoint,
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=2)
        self.assertEqual(raised.exception.code, 401)
        raised.exception.close()

    def test_serves_initialize_tools_list_and_tools_call(self):
        self.start()
        _, initialized = post_json(self.adapter.local_endpoint, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "AI Dev Co-worker Web Chat Gateway")
        _, listed = post_json(self.adapter.local_endpoint, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual([tool["name"] for tool in listed["result"]["tools"]], ["read_file"])
        _, called = post_json(self.adapter.local_endpoint, {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "read_file", "arguments": {"path": "README.md"}},
        })
        self.assertFalse(called["result"]["isError"])
        self.assertEqual(len(self.gateway.activated), 1)
        self.assertEqual(self.gateway.calls, [("read_file", {"path": "README.md"}, "grant-1", 7, self.gateway.activated[0])])

    def test_idle_timeout_stops_listener_and_adapter(self):
        self.start(idle_timeout=0.05)
        deadline = time.time() + 1
        while time.time() < deadline and self.controller.public_state()["status"] != "off":
            time.sleep(0.02)
        self.assertEqual(self.controller.public_state()["status"], "off")
        self.assertTrue(self.adapter.stopped)

    def test_stop_is_idempotent(self):
        self.start()
        generation = self.gateway.activated[-1]
        first = self.controller.stop("manual")
        second = self.controller.stop("manual-again")
        self.assertEqual(first["status"], "off")
        self.assertEqual(second["status"], "off")
        self.assertIn((generation, "manual"), self.gateway.deactivated)

    def test_stop_during_adapter_start_cannot_reconnect_stale_generation(self):
        adapter = BlockingAdapter()
        controller = WebChatTunnelController(adapter_factories={"test": lambda: adapter})
        result = []
        worker = threading.Thread(target=lambda: result.append(controller.start(
            gateway=self.gateway,
            provider="test",
            credential="secret-token",
            expires_at=time.time() + 60,
        )))
        worker.start()
        self.assertTrue(adapter.entered.wait(timeout=1))
        controller.stop("revoked-during-start")
        adapter.release.set()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(controller.public_state()["status"], "off")
        self.assertFalse(controller.public_state()["endpoint"])
        self.assertTrue(adapter.stopped)


class CloudflaredAdapterTests(unittest.TestCase):
    def test_missing_binary_fails_with_actionable_error(self):
        adapter = CloudflaredQuickTunnelAdapter(executable_resolver=lambda: None)
        with self.assertRaisesRegex(RuntimeError, "cloudflared"):
            adapter.start("http://127.0.0.1:1234/mcp")

    def test_discovers_https_endpoint_and_stops_process(self):
        process = FakeProcess("INF Your quick Tunnel has been created https://random.trycloudflare.com\n")
        commands = []
        adapter = CloudflaredQuickTunnelAdapter(
            executable_resolver=lambda: "C:/Tools/cloudflared.exe",
            popen_factory=lambda command, **kwargs: commands.append((command, kwargs)) or process,
            process_tree_killer=lambda target: target.terminate(),
            startup_timeout_seconds=0.2,
        )
        endpoint = adapter.start("http://127.0.0.1:1234/mcp")
        self.assertEqual(endpoint, "https://random.trycloudflare.com/mcp")
        self.assertIn("--no-autoupdate", commands[0][0])
        self.assertNotIn("windowsHide", commands[0][1])
        self.assertTrue(adapter.health())
        adapter.stop()
        self.assertTrue(process.terminated)

    def test_stop_delegates_to_process_tree_cleanup(self):
        process = FakeProcess("INF https://random.trycloudflare.com\n")
        cleaned = []
        adapter = CloudflaredQuickTunnelAdapter(
            executable_resolver=lambda: "cloudflared",
            popen_factory=lambda *_args, **_kwargs: process,
            process_tree_killer=lambda target: cleaned.append(target),
            startup_timeout_seconds=0.2,
        )
        adapter.start("http://127.0.0.1:1234/mcp")
        adapter.stop()
        self.assertEqual(cleaned, [process])


if __name__ == "__main__":
    unittest.main()
