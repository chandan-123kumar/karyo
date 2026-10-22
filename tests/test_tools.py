"""Offline checks for tool dispatch and the model/tool/model loop."""

import json
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch
from huggingface_hub.inference._generated.types.chat_completion import (
    ChatCompletionOutputToolCall,
    ChatCompletionOutputFunctionDefinition,
)

from cli import main
from memory.memory import Memory
from tools.dispatcher import dispatch_tool, dispatch_tool_call
from tools.registry import TOOL_REGISTRY, get_tool_schemas


def response(calls=None, content=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=content, tool_calls=calls,
    ))])


def call(call_id="call_1", name="list_files", arguments='{"path":"tools"}'):
    return ChatCompletionOutputToolCall(id=call_id, type="function", function=ChatCompletionOutputFunctionDefinition(
        name=name, arguments=arguments,
    ))


class ToolTests(unittest.TestCase):
    def test_registered_tool_and_schema(self):
        schemas = get_tool_schemas()
        json.dumps(schemas)
        self.assertIn("list_files", [schema["function"]["name"] for schema in schemas])
        result = dispatch_tool("list_files", '{"path":"tools","pattern":"*.py"}')
        self.assertTrue(result["ok"])
        self.assertIn({"path": "tools/registry.py", "type": "file"}, result["entries"])

    def test_invalid_calls(self):
        cases = [
            ("missing", "{}", "KeyError"),
            ("list_files", "{broken", "JSONDecodeError"),
            ("list_files", "[]", "TypeError"),
            ("list_files", '{"unknown":1}', "TypeError"),
            ("list_files", '{"path":42}', "invalid_argument"),
            ("list_files", '{"path":".."}', "outside_workspace"),
        ]
        for name, arguments, code in cases:
            with self.subTest(arguments=arguments):
                self.assertEqual(dispatch_tool(name, arguments)["error"]["code"], code)

    def test_execution_failure_is_a_result(self):
        handler = Mock(side_effect=RuntimeError("private details"))
        with patch.dict(TOOL_REGISTRY, {"broken": {"handler": handler}}):
            result = dispatch_tool("broken", "{}")
        self.assertEqual(result["error"]["code"], "RuntimeError")
        self.assertNotIn("private details", json.dumps(result))

    def test_error_result_keeps_call_id(self):
        result = dispatch_tool_call(call("abc", "missing", "{}"))
        self.assertEqual(result["tool_call_id"], "abc")
        self.assertEqual(result["role"], "tool")
        self.assertFalse(json.loads(result["content"])["ok"])

    def test_multiple_tools_round_trip_and_followup(self):
        client = Mock()
        requests = []
        responses = iter([
            response([call(), call("call_2", "missing")]),
            response(content="Here are the files."),
            response(content="You asked about files."),
        ])

        def complete(**kwargs):
            requests.append(deepcopy(kwargs))
            return next(responses)

        client.chat.completions.create.side_effect = complete
        memory = Memory()
        with patch("cli.MAX_TOOL_ROUNDS", 2), redirect_stdout(StringIO()):
            main("List files", memory, client)
            main("What did I ask?", memory, client)
        messages = requests[1]["messages"]
        self.assertEqual([message["role"] for message in messages],
                         ["user", "assistant", "tool", "tool"])
        self.assertEqual(messages[2]["tool_call_id"], "call_1")
        self.assertEqual(messages[3]["tool_call_id"], "call_2")
        self.assertIn("tools", requests[0])
        self.assertEqual(requests[2]["messages"][-2]["content"], "Here are the files.")

    def test_round_limit_keeps_results_in_history(self):
        client = Mock()
        client.chat.completions.create.return_value = response([call()])
        memory = Memory()
        with patch("cli.MAX_TOOL_ROUNDS", 2), redirect_stdout(StringIO()) as output:
            main("Keep listing", memory, client)
        self.assertEqual(client.chat.completions.create.call_count, 2)
        self.assertEqual(memory.get_memory()[-1]["role"], "tool")
        self.assertIn("limit", output.getvalue())


if __name__ == "__main__":
    unittest.main()
