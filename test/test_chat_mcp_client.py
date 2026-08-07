import chat_mcp_client as cmc
import json
import tempfile
import time
import unittest
from pathlib import Path

from chat_mcp_client import McpConnectorRegistry, McpDiagnosticsToolProvider, McpToolProvider, SdkMcpClient, create_mcp_clients, validate_connector


class FakeMcpClient:
    def __init__(self):
        self.called = []

    def list_tools(self):
        return [
            {
                "name": "read_event",
                "description": "Read event",
                "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}},
                "annotations": {"readOnlyHint": True},
            },
            {
                "name": "write_event",
                "description": "Write event",
                "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}}},
                "annotations": {"readOnlyHint": False},
            },
        ]

    def call_tool(self, name, arguments):
        self.called.append((name, arguments))
        return {"content": [{"type": "text", "text": f"called {name}"}]}


class FakeRobloxMcpClient:
    def __init__(self, read_only_overrides=None):
        self.called = []
        self.connector = {
            "name": "robloxstudio_mcp",
            "transport": "http",
            "url": "http://localhost:58741/mcp",
            "enabled": True,
            "read_only_overrides": list(read_only_overrides or []),
        }

    def list_tools(self):
        return [
            {
                "name": "get_project_structure",
                "description": "Get full game hierarchy tree.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "maxDepth": {"type": "number"},
                    },
                },
                "annotations": {},
            },
            {
                "name": "get_instance_properties",
                "description": "Get all properties of an instance.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"instancePath": {"type": "string"}},
                    "required": ["instancePath"],
                },
                "annotations": {},
            },
            {
                "name": "create_object",
                "description": "Create a new instance.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "className": {"type": "string"},
                        "parent": {"type": "string"},
                    },
                    "required": ["className", "parent"],
                },
                "annotations": {},
            },
        ]

    def call_tool(self, name, arguments):
        self.called.append((name, arguments))
        return {"content": [{"type": "text", "text": f"called {name}"}]}


class TextishContent:
    type = "text"
    text = "rich MCP text"


class FakeRichMcpResultClient(FakeMcpClient):
    def call_tool(self, name, arguments):
        self.called.append((name, arguments))
        return {"content": [TextishContent()]}


class FailingListToolsClient(FakeMcpClient):
    def list_tools(self):
        raise RuntimeError("server boot failed")


class McpToolProviderTests(unittest.TestCase):
    def test_namespaces_mcp_tools_as_openai_schemas(self):
        provider = McpToolProvider({"calendar": FakeMcpClient()}, approval_callback=lambda _proposal: True)

        names = [schema["function"]["name"] for schema in provider.schemas]

        self.assertEqual(names, ["mcp__calendar__read_event", "mcp__calendar__write_event"])

    def test_mcp_tool_schemas_are_strict_mode_safe(self):
        provider = McpToolProvider({"calendar": FakeMcpClient()}, approval_callback=lambda _proposal: True)

        read_schema = provider.schemas[0]["function"]["parameters"]

        self.assertEqual(read_schema["type"], "object")
        self.assertEqual(read_schema["required"], ["id"])
        self.assertFalse(read_schema["additionalProperties"])

    def test_optional_mcp_schema_properties_become_nullable_for_strict_mode(self):
        class OptionalToolClient(FakeMcpClient):
            def list_tools(self):
                return [
                    {
                        "name": "search",
                        "description": "Search",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "max_results": {"type": "integer"},
                            },
                            "required": ["query"],
                        },
                        "annotations": {"readOnlyHint": True},
                    }
                ]

        provider = McpToolProvider({"search": OptionalToolClient()}, approval_callback=lambda _proposal: True)

        schema = provider.schemas[0]["function"]["parameters"]

        self.assertEqual(schema["required"], ["query", "max_results"])
        self.assertEqual(schema["properties"]["max_results"]["type"], ["integer", "null"])

    def test_nested_optional_mcp_schema_is_strict_and_nullable(self):
        class NestedToolClient(FakeMcpClient):
            def list_tools(self):
                return [
                    {
                        "name": "query",
                        "description": "Nested query",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "filter": {
                                    "type": "object",
                                    "properties": {
                                        "term": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                    "required": ["term"],
                                },
                                "tags": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {"name": {"type": "string"}},
                                    },
                                },
                            },
                        },
                        "annotations": {"readOnlyHint": True},
                    }
                ]

        provider = McpToolProvider({"nested": NestedToolClient()}, approval_callback=lambda _proposal: True)

        schema = provider.schemas[0]["function"]["parameters"]
        filter_schema = schema["properties"]["filter"]
        tag_item_schema = schema["properties"]["tags"]["items"]

        self.assertFalse(filter_schema["additionalProperties"])
        self.assertEqual(filter_schema["required"], ["term", "limit"])
        self.assertEqual(filter_schema["properties"]["limit"]["type"], ["integer", "null"])
        self.assertFalse(tag_item_schema["additionalProperties"])
        self.assertEqual(tag_item_schema["required"], ["name"])

    def test_dispatch_strips_null_arguments_before_calling_mcp_server(self):
        client = FakeMcpClient()
        provider = McpToolProvider({"calendar": client}, approval_callback=lambda _proposal: True)

        payload = json.loads(provider.dispatch("mcp__calendar__read_event", {"id": "1", "optional": None, "nested": {"keep": "x", "drop": None}}))

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(client.called, [("read_event", {"id": "1", "nested": {"keep": "x"}})])

    def test_dispatch_normalizes_rich_mcp_sdk_content_to_json_safe_payload(self):
        client = FakeRichMcpResultClient()
        provider = McpToolProvider({"calendar": client}, approval_callback=lambda _proposal: True)

        payload = json.loads(provider.dispatch("mcp__calendar__read_event", {"id": "1"}))

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["result"]["content"][0], {"type": "text", "text": "rich MCP text"})

    def test_read_only_tool_runs_without_approval(self):
        client = FakeMcpClient()
        approvals = []
        provider = McpToolProvider({"calendar": client}, approval_callback=lambda proposal: approvals.append(proposal) or True)

        payload = json.loads(provider.dispatch("mcp__calendar__read_event", {"id": "1"}))

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(client.called, [("read_event", {"id": "1"})])
        self.assertEqual(approvals, [])

    def test_connector_read_only_overrides_mark_unannotated_tools_read_only(self):
        client = FakeRobloxMcpClient(read_only_overrides=["get_project_structure", "get_instance_properties"])
        approvals = []
        provider = McpToolProvider({"robloxstudio_mcp": client}, approval_callback=lambda proposal: approvals.append(proposal) or True)

        metadata = {item["name"]: item for item in provider.tool_metadata()}
        payload = json.loads(
            provider.dispatch(
                "mcp__robloxstudio_mcp__get_project_structure",
                {"path": "game.Workspace", "maxDepth": 3},
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(metadata["get_project_structure"]["read_only"])
        self.assertTrue(metadata["get_instance_properties"]["read_only"])
        self.assertEqual(client.called, [("get_project_structure", {"path": "game.Workspace", "maxDepth": 3})])
        self.assertEqual(approvals, [])

    def test_unannotated_tools_without_overrides_stay_fail_closed_and_require_approval(self):
        client = FakeRobloxMcpClient()
        approvals = []
        provider = McpToolProvider({"robloxstudio_mcp": client}, approval_callback=lambda proposal: approvals.append(proposal) or False)

        metadata = {item["name"]: item for item in provider.tool_metadata()}
        payload = json.loads(provider.dispatch("mcp__robloxstudio_mcp__get_project_structure", {"path": "game.Workspace"}))

        self.assertEqual(payload["status"], "denied")
        self.assertFalse(metadata["get_project_structure"]["read_only"])
        self.assertEqual(client.called, [])
        self.assertEqual(approvals[0]["tool"], "get_project_structure")

    def test_unknown_or_side_effecting_roblox_tools_still_require_approval(self):
        client = FakeRobloxMcpClient()
        approvals = []
        provider = McpToolProvider({"robloxstudio_mcp": client}, approval_callback=lambda proposal: approvals.append(proposal) or False)

        metadata = {item["name"]: item for item in provider.tool_metadata()}
        payload = json.loads(
            provider.dispatch(
                "mcp__robloxstudio_mcp__create_object",
                {"className": "Part", "parent": "game.Workspace"},
            )
        )

        self.assertEqual(payload["status"], "denied")
        self.assertFalse(metadata["create_object"]["read_only"])
        self.assertEqual(client.called, [])
        self.assertEqual(approvals[0]["server"], "robloxstudio_mcp")
        self.assertEqual(approvals[0]["tool"], "create_object")

    def test_side_effect_tool_requires_approval(self):
        client = FakeMcpClient()
        approvals = []
        provider = McpToolProvider({"calendar": client}, approval_callback=lambda proposal: approvals.append(proposal) or False)

        payload = json.loads(provider.dispatch("mcp__calendar__write_event", {"title": "x"}))

        self.assertEqual(payload["status"], "denied")
        self.assertEqual(client.called, [])
        self.assertEqual(approvals[0]["server"], "calendar")
        self.assertEqual(approvals[0]["tool"], "write_event")

    def test_create_mcp_clients_uses_injected_factory_for_enabled_connectors(self):
        connectors = [
            {"name": "calendar", "transport": "stdio", "command": "calendar-server", "enabled": True},
            {"name": "disabled", "transport": "stdio", "command": "off", "enabled": False},
        ]
        created = []

        def factory(connector):
            created.append(connector["name"])
            return FakeMcpClient()

        clients, statuses = create_mcp_clients(connectors, client_factory=factory)

        self.assertEqual(list(clients), ["calendar"])
        self.assertEqual(created, ["calendar"])
        self.assertEqual(statuses[0]["status"], "connected")
        self.assertEqual(statuses[1]["status"], "disabled")

    def test_connected_status_includes_tool_counts_for_ui_diagnostics(self):
        clients, statuses = create_mcp_clients(
            [{"name": "calendar", "transport": "stdio", "command": "calendar-server", "enabled": True}],
            client_factory=lambda _connector: FakeMcpClient(),
        )

        self.assertEqual(list(clients), ["calendar"])
        self.assertEqual(statuses[0]["status"], "connected")
        self.assertEqual(statuses[0]["tool_count"], 2)
        self.assertEqual(statuses[0]["read_only_tool_count"], 1)
        self.assertEqual(statuses[0]["write_tool_count"], 1)

    def test_connected_roblox_status_counts_consented_override_tools_as_read_only(self):
        clients, statuses = create_mcp_clients(
            [
                {
                    "name": "robloxstudio_mcp",
                    "transport": "http",
                    "url": "http://localhost:58741/mcp",
                    "enabled": True,
                    "read_only_overrides": ["get_project_structure", "get_instance_properties"],
                }
            ],
            client_factory=lambda connector: FakeRobloxMcpClient(read_only_overrides=connector.get("read_only_overrides") or []),
        )

        tools_by_name = {item["name"]: item for item in statuses[0]["tools"]}

        self.assertEqual(list(clients), ["robloxstudio_mcp"])
        self.assertEqual(statuses[0]["status"], "connected")
        self.assertEqual(statuses[0]["tool_count"], 3)
        self.assertEqual(statuses[0]["read_only_tool_count"], 2)
        self.assertEqual(statuses[0]["write_tool_count"], 1)
        self.assertTrue(tools_by_name["get_project_structure"]["read_only"])
        self.assertFalse(tools_by_name["create_object"]["read_only"])

    def test_create_mcp_clients_probes_tool_list_before_reporting_connected(self):
        connectors = [{"name": "broken", "transport": "stdio", "command": "broken-server", "enabled": True}]

        clients, statuses = create_mcp_clients(connectors, client_factory=lambda _connector: FailingListToolsClient())

        self.assertEqual(clients, {})
        self.assertEqual(statuses[0]["status"], "error")
        self.assertIn("server boot failed", statuses[0]["error"])

    def test_create_mcp_clients_reports_missing_sdk_without_crashing(self):
        connectors = [{"name": "calendar", "transport": "stdio", "command": "calendar-server", "enabled": True}]

        clients, statuses = create_mcp_clients(connectors, sdk_available=lambda: False)

        self.assertEqual(clients, {})
        self.assertEqual(statuses[0]["status"], "unavailable")
        self.assertIn("SDK", statuses[0]["error"])

    def test_create_mcp_clients_uses_live_sdk_factory_when_available(self):
        original = cmc._create_sdk_client
        created = []

        def fake_create(connector, **_kwargs):
            created.append(connector)
            return FakeMcpClient()

        cmc._create_sdk_client = fake_create
        try:
            clients, statuses = create_mcp_clients(
                [{"name": "calendar", "transport": "stdio", "command": "calendar-server", "enabled": True}],
                sdk_available=lambda: True,
            )
        finally:
            cmc._create_sdk_client = original

        self.assertEqual(list(clients), ["calendar"])
        self.assertEqual(statuses[0]["status"], "connected")
        self.assertEqual(created[0]["command"], "calendar-server")

    def test_validate_connector_requires_transport_specific_target(self):
        self.assertEqual(validate_connector({"name": "x", "transport": "stdio", "command": "server"})["errors"], [])
        self.assertEqual(validate_connector({"name": "x", "transport": "http", "url": "http://127.0.0.1:3000/mcp"})["errors"], [])
        self.assertEqual(validate_connector({"name": "x", "transport": "sse", "url": "http://127.0.0.1:3000/sse"})["errors"], [])
        self.assertIn("command", validate_connector({"name": "x", "transport": "stdio"})["errors"][0])
        self.assertIn("url", validate_connector({"name": "x", "transport": "http"})["errors"][0])

    def test_http_and_sse_sdk_paths_fail_closed_when_sdk_transport_missing(self):
        for transport in ("http", "sse"):
            client = SdkMcpClient({"name": transport, "transport": transport, "url": "http://127.0.0.1:65535/mcp", "enabled": True})
            with self.assertRaises(RuntimeError) as ctx:
                client.list_tools()
            self.assertIn("MCP SDK", str(ctx.exception))
            self.assertNotIn("not wired", str(ctx.exception))

    def test_create_mcp_clients_times_out_slow_connection(self):
        connectors = [{"name": "slow", "transport": "stdio", "command": "slow-server", "enabled": True}]

        def slow_factory(_connector):
            time.sleep(0.2)
            return FakeMcpClient()

        started = time.monotonic()
        clients, statuses = create_mcp_clients(
            connectors,
            client_factory=slow_factory,
            connection_timeout_seconds=0.01,
        )

        self.assertLess(time.monotonic() - started, 0.15)
        self.assertEqual(clients, {})
        self.assertEqual(statuses[0]["status"], "timeout")
        self.assertIn("timed out", statuses[0]["error"])

    def test_create_mcp_clients_timeout_for_http_roblox_connector_is_actionable(self):
        def slow_factory(_connector):
            time.sleep(0.2)
            return FakeMcpClient()

        clients, statuses = create_mcp_clients(
            [{"name": "robloxstudio_mcp", "transport": "http", "url": "http://localhost:58741/mcp", "enabled": True}],
            client_factory=slow_factory,
            connection_timeout_seconds=0.01,
        )

        self.assertEqual(clients, {})
        self.assertEqual(statuses[0]["status"], "timeout")
        self.assertIn("timed out", statuses[0]["error"])
        self.assertIn("Roblox Studio", statuses[0]["error"])
        self.assertIn("/mcp", statuses[0]["error"])

    def test_create_mcp_clients_reports_actionable_unreachable_http_connector(self):
        class UnreachableMcpClient:
            def probe(self):
                raise RuntimeError("MCP SDK connection failed: All connection attempts failed")

        clients, statuses = create_mcp_clients(
            [{"name": "robloxstudio_mcp", "transport": "http", "url": "http://localhost:58741/mcp", "enabled": True}],
            client_factory=lambda _connector: UnreachableMcpClient(),
        )

        self.assertEqual(clients, {})
        self.assertEqual(statuses[0]["status"], "error")
        self.assertIn("not reachable", statuses[0]["error"])
        self.assertIn("Roblox Studio", statuses[0]["error"])
        self.assertIn("/mcp", statuses[0]["error"])

    def test_mcp_diagnostics_reports_missing_named_connector(self):
        provider = McpDiagnosticsToolProvider(connectors=[], clients={}, statuses=[])

        payload = json.loads(provider.dispatch("mcp_diagnose_connector", {"query": "roblox"}))

        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["found"])
        self.assertIn("No MCP connector matched", payload["message"])

    def test_mcp_diagnostics_reports_connected_tools(self):
        provider = McpDiagnosticsToolProvider(
            connectors=[{"name": "roblox", "transport": "stdio", "command": "roblox-mcp", "enabled": True}],
            clients={"roblox": FakeMcpClient()},
            statuses=[{"name": "roblox", "status": "connected"}],
        )

        payload = json.loads(provider.dispatch("mcp_diagnose_connector", {"query": "test Roblox MCP"}))

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["found"])
        self.assertEqual(payload["matches"][0]["name"], "roblox")
        self.assertEqual(payload["matches"][0]["status"], "connected")
        self.assertEqual(payload["matches"][0]["tools"], ["read_event", "write_event"])

    def test_mcp_diagnostics_generic_test_query_lists_configured_connectors(self):
        provider = McpDiagnosticsToolProvider(
            connectors=[{"name": "robloxstudio_mcp", "transport": "http", "url": "http://localhost:58741/mcp", "enabled": True}],
            clients={"robloxstudio_mcp": FakeMcpClient()},
            statuses=[{"name": "robloxstudio_mcp", "status": "connected"}],
        )

        payload = json.loads(provider.dispatch("mcp_diagnose_connector", {"query": "test"}))

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["found"])
        self.assertEqual(payload["matches"][0]["name"], "robloxstudio_mcp")
        self.assertEqual(payload["matches"][0]["status"], "connected")
        self.assertIn("Configured MCP connector", payload["message"])

    def test_mcp_diagnostics_can_browse_read_only_tool_metadata(self):
        provider = McpDiagnosticsToolProvider(
            connectors=[{"name": "roblox", "transport": "stdio", "command": "roblox-mcp", "enabled": True}],
            clients={"roblox": FakeMcpClient()},
            statuses=[{"name": "roblox", "status": "connected"}],
        )

        payload = json.loads(provider.dispatch("mcp_list_tools", {"query": "roblox"}))

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["servers"][0]["name"], "roblox")
        self.assertEqual(payload["servers"][0]["tools"][0]["name"], "read_event")
        self.assertTrue(payload["servers"][0]["tools"][0]["read_only"])

    def test_mcp_list_tools_listing_is_compact_without_schemas(self):
        provider = McpDiagnosticsToolProvider(
            connectors=[{"name": "roblox", "transport": "stdio", "command": "roblox-mcp", "enabled": True}],
            clients={"roblox": FakeMcpClient()},
            statuses=[{"name": "roblox", "status": "connected"}],
        )

        payload = json.loads(provider.dispatch("mcp_list_tools", {"query": "roblox", "tool": None}))

        for tool in payload["servers"][0]["tools"]:
            self.assertNotIn("input_schema", tool)
            self.assertLessEqual(len(tool["description"]), 100)

    def test_mcp_list_tools_serves_full_schema_for_one_named_tool(self):
        provider = McpDiagnosticsToolProvider(
            connectors=[{"name": "roblox", "transport": "stdio", "command": "roblox-mcp", "enabled": True}],
            clients={"roblox": FakeMcpClient()},
            statuses=[{"name": "roblox", "status": "connected"}],
        )

        payload = json.loads(provider.dispatch("mcp_list_tools", {"query": "roblox", "tool": "read_event"}))

        tools = payload["servers"][0]["tools"]
        self.assertEqual([tool["name"] for tool in tools], ["read_event"])
        self.assertEqual(tools[0]["input_schema"]["type"], "object")
        self.assertFalse(tools[0]["input_schema"]["additionalProperties"])

    def test_sanitize_connector_keeps_deduped_read_only_overrides(self):
        validation = validate_connector(
            {
                "name": "x",
                "transport": "stdio",
                "command": "server",
                "read_only_overrides": [" get_a ", "get_a", "", "get_b"],
            }
        )

        self.assertEqual(validation["connector"]["read_only_overrides"], ["get_a", "get_b"])

    def test_sdk_client_reuses_probed_tool_list_without_second_fetch(self):
        client = SdkMcpClient({"name": "x", "transport": "stdio", "command": "server", "enabled": True})
        fetch_timeouts = []
        client._fetch_tool_list = lambda timeout_seconds: fetch_timeouts.append(timeout_seconds) or [{"name": "t1"}]

        client.probe()
        tools = client.list_tools()

        self.assertEqual(len(fetch_timeouts), 1)
        self.assertEqual(fetch_timeouts[0], client.probe_timeout_seconds)
        self.assertEqual(tools[0]["name"], "t1")

    def test_registry_dedupes_colliding_names_keeping_existing_config_and_unioning_consent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = McpConnectorRegistry(Path(temp_dir))
            registry.save_connectors(
                [
                    {
                        "name": "robloxstudio_mcp",
                        "transport": "http",
                        "url": "http://localhost:58741/mcp",
                        "enabled": True,
                        "read_only_overrides": ["get_selection"],
                    },
                    # A raw preset re-add: sanitizes to the SAME name. Must merge,
                    # never clobber the configured http transport with stdio.
                    {
                        "name": "robloxstudio-mcp",
                        "transport": "stdio",
                        "command": "cmd /c npx -y robloxstudio-mcp@latest",
                        "enabled": False,
                        "read_only_overrides": ["get_selection", "get_project_structure"],
                    },
                ]
            )

            connectors = registry.list_connectors()

            self.assertEqual(len(connectors), 1)
            self.assertEqual(connectors[0]["name"], "robloxstudio_mcp")
            self.assertEqual(connectors[0]["transport"], "http")
            self.assertEqual(connectors[0]["url"], "http://localhost:58741/mcp")
            self.assertTrue(connectors[0]["enabled"])
            self.assertEqual(connectors[0]["read_only_overrides"], ["get_selection", "get_project_structure"])

    def test_exposed_tools_limit_model_schemas_but_not_manual_dispatch(self):
        client = FakeMcpClient()
        client.connector = {"name": "calendar", "exposed_tools": ["read_event"]}
        approvals = []
        provider = McpToolProvider({"calendar": client}, approval_callback=lambda proposal: approvals.append(proposal) or True)

        schema_names = [schema["function"]["name"] for schema in provider.schemas]
        payload = json.loads(provider.dispatch("mcp__calendar__write_event", {"title": "x"}))

        self.assertEqual(schema_names, ["mcp__calendar__read_event"])
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(approvals[0]["tool"], "write_event")

    def test_model_facing_provider_rejects_dispatch_of_unexposed_tools(self):
        client = FakeMcpClient()
        client.connector = {"name": "calendar", "exposed_tools": ["read_event"]}
        provider = McpToolProvider(
            {"calendar": client},
            approval_callback=lambda _proposal: True,
            restrict_dispatch_to_exposed=True,
        )

        payload = json.loads(provider.dispatch("mcp__calendar__write_event", {"title": "x"}))

        self.assertEqual(payload["status"], "error")
        self.assertIn("not exposed", payload["error"])
        self.assertEqual(client.called, [])

    def test_empty_exposed_tools_exposes_every_tool_to_the_model(self):
        provider = McpToolProvider({"calendar": FakeMcpClient()}, approval_callback=lambda _proposal: True)

        schema_names = [schema["function"]["name"] for schema in provider.schemas]

        self.assertEqual(schema_names, ["mcp__calendar__read_event", "mcp__calendar__write_event"])

    def test_strict_schema_leaves_leaf_properties_free_of_object_keywords(self):
        schema = cmc._strict_object_schema(
            {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            }
        )

        self.assertNotIn("properties", schema["properties"]["path"])
        self.assertNotIn("required", schema["properties"]["path"])


if __name__ == "__main__":
    unittest.main()
