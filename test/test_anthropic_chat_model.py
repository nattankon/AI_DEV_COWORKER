import json
import unittest
from unittest.mock import Mock, patch


class _FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class AnthropicChatModelTests(unittest.TestCase):
    @patch("anthropic_chat_model.httpx.post")
    def test_custom_base_url_and_prefix_use_anthropic_messages_contract(self, post):
        from anthropic_chat_model import AnthropicChatModel

        response = Mock()
        response.json.return_value = {"content": [{"type": "text", "text": "OK"}]}
        response.raise_for_status.return_value = None
        post.return_value = response
        model = AnthropicChatModel(
            "custom-secret",
            "anthropic-compatible:claude-sonnet-5",
            base_url="https://proxy.example.com/v1",
            auth_scheme="bearer",
        )

        result = model.complete([{"role": "user", "content": "hello"}], [])

        self.assertEqual(post.call_args.args[0], "https://proxy.example.com/v1/messages")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "claude-sonnet-5")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer custom-secret")
        self.assertNotIn("x-api-key", post.call_args.kwargs["headers"])
        self.assertEqual(result["content"], "OK")

    @patch("anthropic_chat_model.httpx.post")
    def test_translates_openai_style_messages_tools_and_data_url_images(self, post):
        from anthropic_chat_model import AnthropicChatModel

        response = Mock()
        response.json.return_value = {
                "content": [
                    {"type": "text", "text": "I found it."},
                    {"type": "tool_use", "id": "toolu_1", "name": "lookup", "input": {"id": 7}},
                ]
            }
        response.raise_for_status.return_value = None
        post.return_value = response
        model = AnthropicChatModel("sk-ant-test", "anthropic:claude-sonnet-4-20250514", timeout=12)

        result = model.complete(
            [
                {"role": "system", "content": "Follow the user."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Inspect this image."},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
                    ],
                },
                {
                    "role": "assistant",
                    "content": "I will inspect it.",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "lookup", "arguments": "{\"id\": 7}"},
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call_1", "content": "{\"name\": \"Cube\"}"},
            ],
            [
                {
                    "type": "function",
                    "function": {"name": "lookup", "description": "Find an object", "parameters": {"type": "object"}},
                }
            ],
            {"max_tokens": 321, "temperature": 0.2},
        )

        payload = post.call_args.kwargs["json"]
        self.assertEqual(post.call_args.kwargs["headers"]["x-api-key"], "sk-ant-test")
        self.assertEqual(payload["model"], "claude-sonnet-4-20250514")
        self.assertEqual(payload["max_tokens"], 321)
        self.assertEqual(payload["system"], "Follow the user.")
        self.assertEqual(payload["tools"][0]["input_schema"], {"type": "object"})
        self.assertEqual(payload["messages"][0]["content"][1]["source"]["data"], "QUJD")
        self.assertEqual(payload["messages"][1]["content"][1]["type"], "tool_use")
        self.assertEqual(payload["messages"][2]["content"][0]["type"], "tool_result")
        self.assertEqual(result["content"], "I found it.")
        self.assertEqual(json.loads(result["tool_calls"][0]["arguments"]), {"id": 7})


if __name__ == "__main__":
    unittest.main()
