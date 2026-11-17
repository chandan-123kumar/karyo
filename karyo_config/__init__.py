"""Load packaged defaults, user configuration and project overrides."""
import json
import math
import os
from pathlib import Path
from karyo_config.profiles import PROFILE_PROMPTS


class ConfigError(ValueError):
    pass


def load_config(path=None, profile=None):
    defaults = Path(__file__).with_name('defaults.json')
    user = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'karyo' / 'config.json'
    project = Path(path).expanduser() if path else Path.cwd() / 'config.json'
    config = {}
    for source, required in ((defaults, True), (user, False), (project, path is not None)):
        try:
            values = json.loads(source.read_text(encoding='utf-8'))
        except FileNotFoundError:
            if required:
                raise ConfigError(f'Configuration file not found: {source}') from None
            continue
        except (OSError, ValueError):
            raise ConfigError(f'Cannot read valid JSON configuration: {source}') from None
        if not isinstance(values, dict):
            raise ConfigError(f'Configuration must be a JSON object: {source}')
        config.update({key: values[key] for key in ('provider', 'model', 'max_tokens', 'timeout_seconds', 'profile') if key in values})
        # Merge by profile so a project can override investing parameters without
        # discarding the user's general/coding profiles. Each parameter value is
        # replaced as a whole; nested objects such as screen are not deep-merged.
        if 'profiles' in values:
            if not isinstance(values['profiles'], dict):
                raise ConfigError('profiles must be an object keyed by profile name')
            for name, parameters in values['profiles'].items():
                if name not in PROFILE_PROMPTS or not isinstance(parameters, dict):
                    raise ConfigError('Each profiles entry must name a built-in profile and contain an object')
                config.setdefault('profiles', {}).setdefault(name, {}).update(parameters)
    config.setdefault('profile', 'coding')
    config.setdefault('profiles', {})
    if profile is not None:
        config['profile'] = profile
    if not isinstance(config['profile'], str) or config['profile'] not in PROFILE_PROMPTS:
        raise ConfigError('profile must be coding, general, or investing')
    try:
        json.dumps(config['profiles'], allow_nan=False)
    except (ValueError, TypeError):
        raise ConfigError('Profile parameters must contain finite JSON values') from None
    for key in ('provider', 'model'):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ConfigError(f'{key} must be a nonempty string')
    if type(config.get('max_tokens')) is not int or config['max_tokens'] <= 0:
        raise ConfigError('max_tokens must be a positive integer')
    timeout = config.get('timeout_seconds')
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ConfigError('timeout_seconds must be a positive finite number')
    return config
