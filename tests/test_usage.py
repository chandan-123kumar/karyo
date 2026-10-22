import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from cli import main
from memory.memory import Memory
from tests.test_tools import response, call
from token_usage import TokenUsage
from inference import error_details


class UsageTests(unittest.TestCase):
    def test_http_error_diagnostics_and_model_override(self):
        exc = RuntimeError("secret response body")
        exc.response = SimpleNamespace(status_code=404)
        details = error_details(exc)
        self.assertEqual(details["http_status"], 404)
        self.assertIn("--provider", details["message"])
        self.assertNotIn("secret", json.dumps(details))
        client = Mock()
        client.chat.completions.create.return_value = response(content="OK")
        with redirect_stdout(StringIO()):
            main("Hello", Memory(), client, model="example/model")
        self.assertEqual(client.chat.completions.create.call_args.kwargs["model"], "example/model")

    def test_full_trace_captures_each_call_without_later_memory_changes(self):
        first = response([call(name="missing")])
        second = response(content="Done")
        client = Mock()
        client.chat.completions.create.side_effect = [first, second]
        memory = Memory()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calls.jsonl"
            tracker = TokenUsage(path, include_content=True)
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                main("List files", memory, client, tracker)
            memory.save_to_memory("user", "Later message")
            first.choices[0].message.content = "Changed later"
            records = [json.loads(line) for line in path.read_text().splitlines() if json.loads(line).get("event") == "finished"]
        self.assertEqual(records[0]["input"]["messages"], [{"role": "user", "content": "List files"}])
        self.assertIn("tools", records[0]["input"])
        self.assertEqual([m["role"] for m in records[1]["input"]["messages"]], ["user", "assistant", "tool"])
        self.assertEqual(records[0]["output"]["choices"][0]["message"]["tool_calls"][0]["function"]["name"], "missing")
        self.assertEqual(records[1]["output"]["choices"][0]["message"]["content"], "Done")
        self.assertIsNone(tracker.records[0]["output"]["choices"][0]["message"]["content"])

    def test_failed_full_trace_preserves_input_and_null_output(self):
        client = Mock()
        client.chat.completions.create.side_effect = RuntimeError("private error")
        tracker = TokenUsage()
        tracker.include_content = True
        with redirect_stderr(StringIO()), self.assertRaises(RuntimeError):
            main("Hello", Memory(), client, tracker)
        self.assertEqual(tracker.records[0]["input"]["messages"][0]["content"], "Hello")
        self.assertIsNone(tracker.records[0]["output"])
        self.assertNotIn("private error", json.dumps(tracker.records))

    def test_tool_followups_and_session_totals(self):
        first, second = response([call(name="missing")]), response(content="Done")
        first.usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        second.usage = {"prompt_tokens": 150, "completion_tokens": 10, "total_tokens": 160}
        client = Mock()
        client.chat.completions.create.side_effect = [first, second]
        tracker = TokenUsage()
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            main("test", Memory(), client, tracker)
        self.assertEqual(len(tracker.records), 2)
        self.assertIn("input 250 | output 30 | total 280", tracker.summary())

    def test_unknown_counts_are_not_zero(self):
        tracker = TokenUsage()
        with redirect_stderr(StringIO()):
            tracker.record({"usage": {"prompt_tokens": 0, "completion_tokens": 3, "total_tokens": 3}})
            tracker.record({"usage": {"prompt_tokens": -1, "completion_tokens": True}})
        self.assertIsNone(tracker.records[1]["input_tokens"])
        self.assertIsNone(tracker.records[1]["output_tokens"])
        self.assertIn("input 0 (1 request(s) unreported)", tracker.summary())

    def test_failed_request_is_traced_without_error_contents(self):
        client = Mock()
        client.chat.completions.create.side_effect = RuntimeError("private details")
        tracker = TokenUsage()
        with redirect_stderr(StringIO()), self.assertRaises(RuntimeError):
            main("private prompt", Memory(), client, tracker)
        self.assertEqual(tracker.records[0]["status"], "error")
        self.assertIsNone(tracker.records[0]["total_tokens"])
        self.assertNotIn("private", json.dumps(tracker.records))

    def test_jsonl_appends_and_keeps_sessions_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'counts.jsonl'
            for _ in range(2):
                tracker = TokenUsage(path)
                with redirect_stderr(StringIO()):
                    tracker.record({"usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}, "content": "private"})
            records = [json.loads(line) for line in path.read_text().splitlines() if json.loads(line).get("event") == "finished"]
        self.assertEqual(len(records), 2)
        self.assertNotEqual(records[0]["session_id"], records[1]["session_id"])
        self.assertEqual(records[0]["input_tokens"], 2)
        self.assertNotIn("private", json.dumps(records))


if __name__ == '__main__':
    unittest.main()
