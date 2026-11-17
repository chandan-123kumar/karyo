import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

from cli import main, run
from karyo_config import ConfigError, load_config
from memory.memory import Memory
from tests.test_tools import call, response
from trace_viewer import load_sessions, replay_session


class ProfileTests(unittest.TestCase):
    def test_layered_parameters_and_cli_override_do_not_cross_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'karyo').mkdir()
            (root / 'karyo/config.json').write_text(json.dumps({
                'profile': 'investing', 'profiles': {
                    'investing': {'market': 'India', 'screen': {'min_growth': 10}},
                    'general': {'language': 'Hindi'},
                },
            }))
            (root / 'config.json').write_text(json.dumps({
                'profiles': {'investing': {'currency': 'INR', 'screen': {'max_debt': 1}}},
            }))
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}), patch('pathlib.Path.cwd', return_value=root):
                config = load_config()
                self.assertEqual(config['profile'], 'investing')
                self.assertEqual(config['profiles']['investing'], {
                    'market': 'India', 'currency': 'INR', 'screen': {'max_debt': 1},
                })
                config = load_config(profile='general')
                self.assertEqual(config['profile'], 'general')
                self.assertEqual(config['profiles']['general'], {'language': 'Hindi'})

    def test_invalid_profile_config_is_rejected(self):
        invalid_values = [
            {'profile': 'unknown'}, {'profile': []}, {'profiles': []},
            {'profiles': {'investing': 'instructions'}},
            {'profiles': {'unknown': {}}},
            {'profiles': {'investing': {'budget': float('nan')}}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
                for values in invalid_values:
                    with self.subTest(values=values):
                        path.write_text(json.dumps(values))
                        with self.assertRaises(ConfigError):
                            load_config(path)

    def test_selected_profile_reaches_every_request_without_changing_history(self):
        client = Mock()
        client.chat.completions.create.side_effect = [
            response([call(name='missing')]), response(content='Done'),
        ]
        memory = Memory()
        with redirect_stdout(StringIO()):
            main('Screen my watchlist', memory, client, model='test', max_tokens=100,
                 profile='investing', profile_parameters={'market': 'India', 'currency': 'INR'})
        self.assertEqual(client.chat.completions.create.call_count, 2)
        for request in client.chat.completions.create.call_args_list:
            prompt = request.kwargs['messages'][0]['content']
            self.assertIn('Active profile: investing.', prompt)
            self.assertIn('"currency": "INR"', prompt)
            self.assertNotIn('Active profile: coding.', prompt)
        self.assertFalse(any(m['role'] == 'system' for m in memory.get_memory()))

    def test_profile_defaults_to_coding(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}), patch('pathlib.Path.cwd', return_value=Path(directory)):
                self.assertEqual(load_config()['profile'], 'coding')

    def test_cli_override_selects_parameters_and_records_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            path.write_text(json.dumps({
                'profile': 'general', 'profiles': {'investing': {'currency': 'INR'}},
            }))
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': directory, 'XDG_DATA_HOME': directory}), \
                    patch('sys.argv', ['karyo', '--config', str(path), '--profile', 'investing']), \
                    patch('cli.create_client'), patch('cli.main') as agent, \
                    patch('tools.mcp_client.MCPClientManager') as manager, \
                    patch('builtins.input', side_effect=['Analyze my portfolio', '/exit']), \
                    redirect_stdout(StringIO()) as output:
                manager.return_value.start.return_value = []
                manager.return_value.errors = []
                self.assertEqual(run(), 0)
            self.assertIn('Profile: investing', output.getvalue())
            self.assertEqual(agent.call_args.kwargs['profile'], 'investing')
            self.assertEqual(agent.call_args.kwargs['profile_parameters'], {'currency': 'INR'})
            session = load_sessions(Path(directory) / 'karyo/traces')['sessions'][0]
            event = next(e for e in session['events'] if e['event'] == 'profile_configured')
            self.assertEqual(event['parameters'], {'currency': 'INR'})

    def test_replay_keeps_original_profile_instead_of_current_default(self):
        source = {
            'project': str(Path.cwd()), 'id': 'original', 'events': [
                {'event': 'profile_configured', 'profile': 'investing', 'parameters': {'market': 'India'}},
                {'event': 'user_query', 'content': 'Compare my watchlist'},
            ],
        }
        with tempfile.TemporaryDirectory() as directory, \
                patch('karyo_config.load_config', return_value={
                    'provider': 'test', 'model': 'test', 'timeout_seconds': 10,
                    'max_tokens': 100, 'profile': 'coding', 'profiles': {},
                }), patch('inference.create_client'), patch('harness_auth.read_token', return_value='test'), \
                patch('tools.mcp_client.MCPClientManager'), patch('cli.main') as agent:
            replay_session(directory, source)
            agent.assert_called_once()
            self.assertEqual(agent.call_args.kwargs['profile'], 'investing')
            self.assertEqual(agent.call_args.kwargs['profile_parameters'], {'market': 'India'})
            replay = load_sessions(directory)['sessions'][0]
            self.assertEqual(replay['status'], 'closed')


if __name__ == '__main__':
    unittest.main()
