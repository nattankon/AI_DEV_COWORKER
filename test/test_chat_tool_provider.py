import json
import unittest

from chat_tool_provider import CompositeToolProvider


class FakeProvider:
    def __init__(self, prefix, result):
        self.schemas = [
            {
                "type": "function",
                "function": {
                    "name": f"{prefix}_tool",
                    "description": "fake",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        self.result = result
        self.calls = []

    def dispatch(self, name, arguments):
        self.calls.append((name, arguments))
        return json.dumps({"status": "ok", "result": self.result})


class CompositeToolProviderTests(unittest.TestCase):
    def test_merges_schemas_and_routes_dispatch(self):
        left = FakeProvider("left", "L")
        right = FakeProvider("right", "R")
        provider = CompositeToolProvider([left, right])

        self.assertEqual([schema["function"]["name"] for schema in provider.schemas], ["left_tool", "right_tool"])
        self.assertEqual(json.loads(provider.dispatch("right_tool", {"x": 1}))["result"], "R")
        self.assertEqual(right.calls, [("right_tool", {"x": 1})])
        self.assertEqual(left.calls, [])

    def test_rejects_name_collisions(self):
        first = FakeProvider("same", "a")
        second = FakeProvider("same", "b")

        with self.assertRaisesRegex(ValueError, "Tool name collision"):
            CompositeToolProvider([first, second])

    def test_unknown_tool_returns_standard_error_shape(self):
        provider = CompositeToolProvider([FakeProvider("known", "ok")])

        payload = json.loads(provider.dispatch("missing", {}))

        self.assertEqual(payload["status"], "error")
        self.assertIn("Unknown tool", payload["error"])


if __name__ == "__main__":
    unittest.main()
