"""Load packaged defaults, user configuration and project overrides."""
import json
import math
import os
import tempfile
from pathlib import Path
from karyo_config.profiles import PROFILE_PROMPTS


class ConfigError(ValueError):
    pass


def save_profile_config(path, profile, parameters):
    """Atomically save a profile while preserving unrelated configuration."""
    path = Path(path).expanduser()
    try:
        values = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        values = {}
    except (OSError, ValueError):
        raise ConfigError('Cannot save: existing configuration is unreadable or invalid JSON') from None
    if not isinstance(values, dict) or not isinstance(values.get('profiles', {}), dict):
        raise ConfigError('Cannot save: configuration and profiles must be objects')
    if profile not in PROFILE_PROMPTS or not isinstance(parameters, dict):
        raise ConfigError('Cannot save: invalid profile or parameters')
    values['profile'] = profile
    values.setdefault('profiles', {})[profile] = parameters
    try:
        content = json.dumps(values, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    except (TypeError, ValueError):
        raise ConfigError('Cannot save: parameters must contain finite JSON values') from None
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.karyo-config-', delete=False) as stream:
            temporary_path = Path(stream.name)
            stream.write(content)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


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
