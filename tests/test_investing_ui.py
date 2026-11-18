import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from cli import run
from karyo_config import ConfigError, load_config, save_profile_config
from karyo_config.investing_ui import configure_investing
from trace_viewer import load_sessions, replay_session


class InvestingUITests(unittest.TestCase):
    def configure(self, parameters, answers):
        with patch('builtins.input', side_effect=answers), redirect_stdout(StringIO()):
            return configure_investing(parameters)

    def test_setup_preserves_screening_parameters_and_does_not_mutate_input(self):
        original = {'screen': {'min_growth': 10}}
        result = self.configure(original, ['1', '', '2', '1', '10000', '500', ''])
        self.assertEqual(result, {
            'screen': {'min_growth': 10}, 'market': 'India', 'currency': 'INR',
            'holding_period': 'Several days', 'experience': 'Beginner',
            'capital': 10000, 'max_loss': 500,
        })
        self.assertEqual(original, {'screen': {'min_growth': 10}})

    def test_invalid_choices_and_amounts_retry_without_accepting_nonfinite_values(self):
        result = self.configure({}, [
            'invalid', '2', 'dollars', 'usd', '3', '2',
            'abc', 'nan', 'inf', '-1', '0', '1000', '-1', '1001', '50', 'yes',
        ])
        self.assertEqual(result['currency'], 'USD')
        self.assertEqual(result['capital'], 1000)
        self.assertEqual(result['max_loss'], 50)

    def test_cancel_and_decline_discard_partial_changes(self):
        original = {'market': 'India', 'currency': 'INR', 'capital': 1000, 'max_loss': 100}
        self.assertIsNone(self.configure(original, ['US', '/cancel']))
        self.assertIsNone(self.configure(original, ['', '', '', '', '', '', 'n']))
        self.assertEqual(original['market'], 'India')
        self.assertEqual(original['capital'], 1000)

    def test_currency_change_requires_new_amounts(self):
        original = {'market': 'India', 'currency': 'INR', 'capital': 100000, 'max_loss': 5000}
        result = self.configure(original, ['2', '', '2', '1', '', '', ''])
        self.assertEqual(result['currency'], 'USD')
        self.assertIsNone(result['capital'])
        self.assertIsNone(result['max_loss'])

    def test_clear_amounts_and_lower_capital_revalidates_loss_limit(self):
        original = {'market': 'India', 'currency': 'INR', 'capital': 1000, 'max_loss': 500}
        result = self.configure(original, ['', '', '', '', '100', '', '0', ''])
        self.assertEqual(result['capital'], 100)
        self.assertEqual(result['max_loss'], 0)
        result = self.configure(original, ['', '', '', '', 'clear', 'clear', ''])
        self.assertIsNone(result['capital'])
        self.assertIsNone(result['max_loss'])

    def test_save_preserves_other_settings_and_refuses_invalid_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps({'provider': 'test', 'custom': True,
                                       'profiles': {'general': {'language': 'Hindi'}}}))
            save_profile_config(path, 'investing', {'currency': 'INR', 'capital': 1000})
            saved = json.loads(path.read_text())
            self.assertEqual(saved['provider'], 'test')
            self.assertTrue(saved['custom'])
            self.assertEqual(saved['profiles']['general'], {'language': 'Hindi'})
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
                config = load_config(path)
            self.assertEqual(config['profile'], 'investing')
            self.assertEqual(config['profiles']['investing']['capital'], 1000)
            path.write_text('{invalid')
            with self.assertRaises(ConfigError):
                save_profile_config(path, 'investing', {})
            self.assertEqual(path.read_text(), '{invalid')

    def test_terminal_setup_reaches_model_and_explicit_save_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text('{"profile": "general", "provider": "test"}')
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': directory, 'XDG_DATA_HOME': directory}), \
                    patch('sys.argv', ['karyo', '--config', str(path)]), \
                    patch('cli.create_client'), patch('cli.main') as agent, \
                    patch('tools.mcp_client.MCPClientManager') as manager, \
                    patch('builtins.input', side_effect=[
                        '/investing setup', '1', '', '2', '1', '10000', '500', '',
                        '/investing', 'Research opportunities', '/investing save', '/exit',
                    ]), redirect_stdout(StringIO()) as output:
                manager.return_value.start.return_value = []
                manager.return_value.errors = []
                self.assertEqual(run(), 0)
            agent.assert_called_once()
            self.assertEqual(agent.call_args.kwargs['profile'], 'investing')
            parameters = agent.call_args.kwargs['profile_parameters']
            self.assertEqual(parameters['max_loss'], 500)
            self.assertEqual(json.loads(path.read_text())['profiles']['investing'], parameters)
            self.assertIn('Investing settings saved', output.getvalue())
            session = load_sessions(Path(directory) / 'karyo/traces')['sessions'][0]
            events = [event for event in session['events'] if event['event'] == 'profile_configured']
            self.assertEqual([event['profile'] for event in events], ['general', 'investing'])

    def test_replay_applies_settings_changes_before_each_question(self):
        source = {'id': 'original', 'project': str(Path.cwd()), 'events': [
            {'event': 'profile_configured', 'profile': 'investing', 'parameters': {'capital': 1000}},
            {'event': 'user_query', 'content': 'First question'},
            {'event': 'profile_configured', 'profile': 'investing', 'parameters': {'capital': 2000}},
            {'event': 'user_query', 'content': 'Second question'},
        ]}
        with tempfile.TemporaryDirectory() as directory, \
                patch('karyo_config.load_config', return_value={
                    'provider': 'test', 'model': 'test', 'timeout_seconds': 10,
                    'max_tokens': 100, 'profile': 'coding', 'profiles': {},
                }), patch('inference.create_client'), patch('harness_auth.read_token', return_value='test'), \
                patch('tools.mcp_client.MCPClientManager'), patch('cli.main') as agent:
            replay_session(directory, source)
            self.assertEqual([call.kwargs['profile_parameters']['capital']
                              for call in agent.call_args_list], [1000, 2000])


if __name__ == '__main__':
    unittest.main()
