"""Derive stable asset references without keeping a second creative asset ledger."""
from __future__ import annotations

from decimal import Decimal
from pathlib import PureWindowsPath
import re
import unicodedata

from .contracts import require
from .profiles import validate_schema

_RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)', re.I)
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(name):
    require(isinstance(name, str) and bool(name.strip()), 'name: expected nonempty text')
    normalized = unicodedata.normalize('NFC', name)
    require(not _INVALID.search(normalized), f'name: Windows-invalid characters: {name!r}')
    require(normalized not in {'.', '..'} and not normalized.endswith((' ', '.')),
            f'name: trailing dot/space or traversal is not permitted: {name!r}')
    require(not _RESERVED.match(normalized), f'name: Windows reserved name: {name!r}')
    require(len(normalized.encode('utf-16-le')) // 2 <= 255, 'name: component exceeds 255 UTF-16 units')
    return normalized


def canonical_filename(asset_id, display_name, state, view, revision, suffix='.png'):
    require(type(revision) is int and revision > 0, 'revision: expected positive integer')
    require(suffix in {'.png', '.jpg', '.jpeg', '.webp'}, 'suffix: unsupported image format')
    parts = [safe_name(x) for x in (asset_id, display_name, state, view)]
    return safe_name('_'.join(parts) + f'_r{revision:03d}' + suffix)


def ensure_unique_names(names):
    seen = set()
    normalized = []
    for name in names:
        value = safe_name(name)
        key = value.casefold()
        require(key not in seen, f'name: case/Unicode collision: {name!r}')
        seen.add(key)
        normalized.append(value)
    return normalized


def safe_relative_file(value, max_path_units=240, root=None):
    require(isinstance(value, str) and value, 'file: expected relative path')
    path = PureWindowsPath(value)
    require(not path.is_absolute() and not path.drive and not path.root and '..' not in path.parts,
            'file: expected relative path without traversal or drive')
    for component in path.parts:
        safe_name(component)
    require(len(value.encode('utf-16-le')) // 2 <= max_path_units, 'file: relative path exceeds configured length')
    if root is not None:
        resolved = PureWindowsPath(root) / path
        require(len(str(resolved).encode('utf-16-le')) // 2 <= max_path_units,
                'file: resolved path exceeds configured length')
    return value.replace('\\', '/')


def registry_check(assets, media=None, shot_ids=None):
    validate_schema('assets', assets)
    ids, keys, filenames = set(), {}, []
    available_shots = set(shot_ids) if shot_ids is not None else None
    for asset in assets['items']:
        identity = asset['id']
        require(identity not in ids, f'assets.{identity}: duplicate asset id')
        ids.add(identity)
        require(asset.get('asset_id', identity) == identity, f'assets.{identity}.asset_id: alias mismatch')
        safe_name(identity)
        safe_name(asset['display_name'])
        if available_shots is not None:
            require(set(asset['shot_ids']) <= available_shots, f'assets.{identity}.shot_ids: unknown shot')
        states = {s['state_id']: s for s in asset['states']}
        require(len(states) == len(asset['states']), f'assets.{identity}.states: duplicate state_id')
        for state in asset['states']:
            safe_name(state['state_id'])
            require(set(state['shot_ids']) <= set(asset['shot_ids']), f'assets.{identity}.states: unknown asset shot')
        require({shot for state in asset['states'] for shot in state['shot_ids']} == set(asset['shot_ids']),
                f'assets.{identity}.states: must cover asset shots')
        for ref in asset['media_requirements']:
            key = ref['reference_key']
            require(key not in keys, f'assets.{identity}.reference_key: duplicate {key}')
            require(ref['state_id'] in states, f'assets.{identity}.media_requirements: unknown state')
            require(ref['coverage_policy'] != 'scene_reference' or asset['kind'] == 'prop',
                    f'assets.{identity}: only props may use scene reference coverage')
            safe_name(ref['view'])
            require(ref['coverage_policy'] != 'scene_reference' or bool(ref.get('covered_by_reference_key')),
                    f'assets.{identity}: scene coverage requires covered_by_reference_key')
            require(not asset.get('interaction_critical', False) or ref['coverage_policy'] == 'independent',
                    f'assets.{identity}: interaction-critical prop requires independent reference')
            keys[key] = {'asset_id': identity, 'kind': asset['kind'], **ref}
    for key, ref in keys.items():
        covered = ref.get('covered_by_reference_key')
        if ref['coverage_policy'] == 'scene_reference':
            require(covered in keys and keys[covered]['kind'] == 'space' and keys[covered]['coverage_policy'] == 'independent',
                    f'assets.{key}: scene coverage must point to an independent space reference')
    if media is None:
        return keys
    require(isinstance(media, dict) and isinstance(media.get('items'), list), 'media.items: expected array')
    seen = set()
    for row in media['items']:
        validate_schema('media_reference', row)
        key = row['reference_key']
        require(key in keys, f'media.{key}: unknown reference_key')
        require(key not in seen, f'media.{key}: duplicate reference')
        seen.add(key)
        safe_relative_file(row['file'])
        safe_relative_file(row['review_ref']['path'])
        safe_name(row['canonical_name'])
        require(PureWindowsPath(row['file']).stem == row['canonical_name'],
                f'media.{key}.canonical_name: must equal file stem')
        filenames.append(PureWindowsPath(row['file']).name)
    ensure_unique_names(filenames)
    required = {k for k, row in keys.items() if row['required'] and row['coverage_policy'] == 'independent'}
    required.update(row['covered_by_reference_key'] for row in keys.values()
                    if row['required'] and row['coverage_policy'] == 'scene_reference')
    require(required <= seen, 'media.items: missing required references: ' + ', '.join(sorted(required - seen)))
    return keys


def storyboard_check(value, inputs):
    validate_schema('storyboard', value)
    items = value['items']
    ids = [x['id'] for x in items]
    require(len(set(ids)) == len(ids), 'storyboard.items: duplicate shot id')
    require([x['order'] for x in items] == list(range(1, len(items) + 1)), 'storyboard.items: order must be contiguous from 1')
    for row in items:
        require('duration_seconds' not in row, f"storyboard.{row['id']}: use duration_ms only")
        require(row.get('shot_id', row['id']) == row['id'], f"storyboard.{row['id']}.shot_id: alias mismatch")
    brief = inputs.get('brief', {})
    if 'duration_ms' in brief:
        total = brief['duration_ms']
        require(type(total) is int and total > 0, 'brief.duration_ms: expected positive integer')
    else:
        milliseconds = Decimal(str(brief['duration_seconds'])) * 1000
        require(milliseconds == milliseconds.to_integral_value(), 'brief.duration_seconds: fractional milliseconds unsupported')
        total = int(milliseconds)
    require(sum(x['duration_ms'] for x in items) == total, 'storyboard.duration_ms: total does not match brief')
    story = inputs.get('story')
    if story is not None:
        require({x['scene_id'] for x in items} == {x['id'] for x in story['items']},
                'storyboard.scene_id: must cover exactly the story scenes')
    assets = inputs.get('assets')
    if assets is not None:
        registry_check(assets, shot_ids=ids)
        known = {x['id']: {s['state_id'] for s in x['states']} for x in assets['items']}
        for shot in items:
            for binding in shot['asset_bindings']:
                require(binding['asset_id'] in known and binding['state_id'] in known[binding['asset_id']],
                        f"storyboard.{shot['id']}.asset_bindings: unknown asset or state")
    return value


def story_check(value, inputs):
    validate_schema('story', value)
    ids = [x['id'] for x in value['items']]
    require(len(set(ids)) == len(ids), 'story.items: duplicate scene id')
    for row in value['items']:
        require('duration_seconds' not in row, f"story.{row['id']}: use duration_ms only")
    brief = inputs['brief']
    if 'duration_ms' in brief:
        total = brief['duration_ms']
        require(type(total) is int and total > 0, 'brief.duration_ms: expected positive integer')
    else:
        milliseconds = Decimal(str(brief['duration_seconds'])) * 1000
        require(milliseconds == milliseconds.to_integral_value(), 'brief.duration_seconds: fractional milliseconds unsupported')
        total = int(milliseconds)
    require(sum(x['duration_ms'] for x in value['items']) == total, 'story.duration_ms: total does not match brief')
    return value
