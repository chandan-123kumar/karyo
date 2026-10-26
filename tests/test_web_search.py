import json
import unittest
from io import BytesIO
from unittest.mock import patch

from tools.dispatcher import dispatch_tool
from tools.registry import get_tool_schemas
from tools.web_search import web_search


class WebSearchTests(unittest.TestCase):
    def test_schema_is_registered(self):
        schemas = get_tool_schemas()
        self.assertIn("web_search", [schema["function"]["name"] for schema in schemas])
        json.dumps(schemas)

    def test_search_returns_parsed_results(self):
        page = b'''<div class="result">
          <a class="result__a" href="https://example.com/page">Example <b>Page</b></a>
          <a class="result__snippet">Useful <b>snippet</b></a>
        </div>'''
        with patch("tools.web_search.urlopen", return_value=BytesIO(page)):
            result = dispatch_tool("web_search", '{"query":"example","max_results":2}')
        self.assertTrue(result["ok"])
        self.assertEqual(result["results"][0], {
            "title": "Example Page", "url": "https://example.com/page",
            "snippet": "Useful snippet",
        })
        self.assertIn("untrusted", result["note"])

    def test_rejects_bad_limits_without_network_request(self):
        with patch("tools.web_search.urlopen") as open_url:
            result = web_search("example", max_results=11)
        self.assertEqual(result["error"]["code"], "invalid_max_results")
        open_url.assert_not_called()

    def test_network_errors_are_structured(self):
        with patch("tools.web_search.urlopen", side_effect=TimeoutError):
            result = web_search("example")
        self.assertEqual(result, {"ok": False, "error": {"code": "network_error"}})


if __name__ == "__main__":
    unittest.main()
