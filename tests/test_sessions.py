import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch
from cli import run, main
from memory.memory import Memory
from tests.test_tools import response, call
from token_usage import TokenUsage
from trace_viewer import load_sessions


class SessionTests(unittest.TestCase):
    def test_empty_launch_is_saved_and_closed(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME': directory}), patch('sys.argv', ['karyo']), patch('cli.create_client'), patch('builtins.input', return_value='/exit'), redirect_stdout(StringIO()):
            self.assertEqual(run(), 0)
            session = load_sessions(Path(directory) / 'karyo/traces')['sessions'][0]
            self.assertEqual(session['status'], 'closed')
            self.assertEqual(session['calls'], [])
            self.assertEqual(session['events'][0]['event'], 'session_started')
            self.assertEqual(session['events'][-1]['event'], 'session_ended')

    def test_turns_and_tool_events_survive_without_followup(self):
        with tempfile.TemporaryDirectory() as directory:
            tracker = TokenUsage(Path(directory) / 'session.jsonl', include_content=True)
            tracker.begin_session()
            client = Mock()
            client.chat.completions.create.side_effect = [response([call(name='missing')]), response(content='Second answer')]
            with patch('cli.MAX_TOOL_ROUNDS', 1), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                main('First question', Memory(), client, tracker)
                main('Second question', Memory(), client, tracker)
            tracker.end_session()
            session = load_sessions(directory)['sessions'][0]
        events = session['events']
        self.assertEqual([e['content'] for e in events if e['event']=='user_query'], ['First question','Second question'])
        self.assertEqual([e['turn'] for e in events if e['event']=='user_query'], [1,2])
        result = next(e for e in events if e['event']=='tool_result')
        self.assertEqual(result['request'], 1)
        self.assertEqual(result['result']['tool_call_id'], 'call_1')
        self.assertEqual(len(session['calls']), 2)
        self.assertEqual(session['calls'][1]['turn'], 2)

    def test_initialization_failure_closes_session_with_error(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME': directory}), patch('sys.argv', ['karyo']), patch('cli.create_client', side_effect=RuntimeError('private')), redirect_stdout(StringIO()):
            self.assertEqual(run(), 1)
            session = load_sessions(Path(directory) / 'karyo/traces')['sessions'][0]
            self.assertEqual(session['status'], 'error')
            self.assertNotIn('private', json.dumps(session))


if __name__ == '__main__':
    unittest.main()
