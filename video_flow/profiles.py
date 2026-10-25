"""Versioned production configuration and finite platform capability contracts."""
from __future__ import annotations

from pathlib import Path
from datetime import date
import math
import json
import re
from string import Formatter

from jsonschema import Draft202012Validator
import yaml

from .contracts import FlowError, require

SCHEMA_ROOT = Path(__file__).resolve().parent / 'schemas' / 'v02'


def validate_schema(name, value):
    schema = json.loads((SCHEMA_ROOT / (name + '.schema.json')).read_text(encoding='utf-8'))
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(list(e.absolute_path)))
    if errors:
        error = errors[0]
        location = '.'.join(str(x) for x in error.absolute_path) or '$'
        raise FlowError(f'{name}.{location}: {error.message}')
    return value


def production_config_check(config):
    validate_schema('production_config', config)
    cost = config['budget']['max_total_cost']
    require(cost is None or math.isfinite(cost), 'production_config.budget.max_total_cost: expected finite number')
    for literal, field, spec, conversion in Formatter().parse(config['delivery']['directory_name']):
        require(not any(x in literal for x in '<>:"/\\|?*') and all(ord(x) >= 32 for x in literal),
                'production_config.delivery.directory_name: invalid filename characters')
        require(field is None or (field in {'title', 'revision'} and not conversion
                and (not spec or (field == 'revision' and re.fullmatch(r'0?[1-9]?[0-9]?d', spec)))),
                'production_config.delivery.directory_name: only title/revision fields and integer revision format supported')
    if config['media_mode'] == 'generate' and config['budget']['paid_generation_authorized']:
        require(config['budget']['max_total_cost'] is not None,
                'production_config.budget.max_total_cost: authorized paid generation needs a finite budget')
    return config


def platform_profile_check(profile):
    validate_schema('platform_profile', profile)
    for name, mode in profile['modes'].items():
        require(mode['min_duration_ms'] <= mode['max_duration_ms'],
                f'platform_profile.modes.{name}: minimum duration exceeds maximum')
    if profile['status'] == 'verified':
        require(profile.get('verified_at') is not None,
                'platform_profile.verified_at: verified profiles require verification date')
    if profile['verified_at'] is not None:
        try:
            date.fromisoformat(profile['verified_at'])
        except ValueError as exc:
            raise FlowError('platform_profile.verified_at: invalid calendar date') from exc
    return profile


def provider_profile_check(profile):
    validate_schema('provider_profile', profile)
    env = profile.get('credential_env')
    require(env is None or re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', env),
            'provider_profile.credential_env: expected environment variable name, not a credential')
    require(profile['status'] != 'test_only' or profile['test_only'],
            'provider_profile.test_only: test status must retain test_only=true')
    return profile


def load_production_bundle(path):
    """Read user-selected YAML and profiles; runtime uses the returned locked copies."""
    path = Path(path).resolve()
    def read_yaml(source):
        value = yaml.safe_load(source.read_text(encoding='utf-8-sig'))
        require(isinstance(value, dict), f'{source.name}: expected a configuration object')
        return value
    production = production_config_check(read_yaml(path))
    def local_profile(value):
        relative = Path(value)
        require(not relative.is_absolute() and '..' not in relative.parts,
                'production_config.profile: expected local relative path without traversal')
        resolved = (path.parent / relative).resolve()
        require(resolved.is_relative_to(path.parent), 'production_config.profile: profile escapes configuration directory')
        return resolved
    platform = platform_profile_check(read_yaml(local_profile(production['platform_profile'])))
    provider = provider_profile_check(read_yaml(local_profile(production['provider_profile'])))
    require(production['selected_mode'] in platform['modes'], 'production_config.selected_mode: unknown platform mode')
    target = production.get('target_segment_duration_ms')
    mode = platform['modes'][production['selected_mode']]
    require(target is None or mode['min_duration_ms'] <= target <= mode['max_duration_ms'],
            'production_config.target_segment_duration_ms: outside selected mode duration limits')
    if production['media_mode'] == 'generate':
        require(not provider['test_only'], 'provider_profile.test_only: test provider cannot generate production images')
    if production['media_mode'] != 'mock':
        require(platform['status'] != 'test_only', 'platform_profile.status: test profile requires mock media mode')
    return {'production': production, 'platform': platform, 'provider': provider}
