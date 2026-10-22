import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from karyo_config import load_config, ConfigError
from inference import create_client


class ConfigTests(unittest.TestCase):
    def test_defaults_and_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}), patch('pathlib.Path.cwd', return_value=root):
                self.assertEqual(load_config()['provider'], 'featherless-ai')
                (root / 'karyo').mkdir()
                (root / 'karyo/config.json').write_text(json.dumps({'provider': 'user-provider'}))
                self.assertEqual(load_config()['provider'], 'user-provider')
                (root / 'config.json').write_text(json.dumps({'provider': 'project-provider'}))
                self.assertEqual(load_config()['provider'], 'project-provider')
                explicit = root / 'other.json'
                explicit.write_text(json.dumps({'provider': 'explicit-provider'}))
                self.assertEqual(load_config(explicit)['provider'], 'explicit-provider')
                explicit.write_text('{"timeout_seconds": -1}')
                with self.assertRaises(ConfigError):
                    load_config(explicit)

    def test_client_reads_configuration_and_accepts_override(self):
        with patch('inference.load_config', return_value={'provider':'configured', 'timeout_seconds':12}), patch('inference.read_token', return_value='test'), patch('inference.InferenceClient') as client:
            create_client()
            client.assert_called_with(provider='configured', api_key='test', timeout=12)
            create_client(provider='override', timeout=25)
            client.assert_called_with(provider='override', api_key='test', timeout=25)


if __name__ == '__main__':
    unittest.main()
