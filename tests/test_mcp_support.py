import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock

from cli import main
from memory.memory import Memory
from tests.test_tools import call, response


class MCPSupportTests(unittest.TestCase):
    def test_model_receives_allowlisted_mcp_schema_and_dispatches_call(self):
        schema = {
            "type": "function",
            "function": {
                "name": "mcp_aws_docs_search_documentation",
                "description": "Search AWS documentation",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                               "required": ["query"]},
            },
        }
        manager = SimpleNamespace(
            tools=[{"schema": schema}],
            tool_names={"mcp_aws_docs_search_documentation"},
            call_tool=Mock(return_value={"ok": True, "content": "AWS docs result"}),
        )
        client = Mock()
        requests = []
        responses = iter([
            response([call("mcp-1", "mcp_aws_docs_search_documentation", '{"query":"S3"}')]),
            response(content="Here is the AWS documentation result."),
        ])

        def capture(**kwargs):
            requests.append(kwargs)
            return next(responses)

        client.chat.completions.create.side_effect = capture
        with redirect_stdout(StringIO()):
            main("Search AWS docs for S3", Memory(), client, mcp_manager=manager)

        exposed = [tool["function"]["name"] for tool in requests[0]["tools"]]
        self.assertIn("mcp_aws_docs_search_documentation", exposed)
        manager.call_tool.assert_called_once_with(
            "mcp_aws_docs_search_documentation", {"query": "S3"}
        )


if __name__ == "__main__":
    unittest.main()
