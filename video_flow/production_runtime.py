"""v0.2 production behavior, isolated from the legacy protocol."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from .contracts import require, artifact_check, media_item_check
from .storage import read, inside, digest


def materialize_workflow(workflow, production=False):
    result = deepcopy(workflow)
    rows = []
    for row in result['stages']:
        if row.pop('production_only', False) and not production:
            continue
        override = row.pop('production', {})
        if production:
            row.update(override)
        rows.append(row)
    result['stages'] = rows
    if production:
        result['version'] = '0.2.0'
        result['delivery_level'] = 'external_production_package'
    return result


def enabled(state):
    return state.get('version') == '0.2.0'


def bundle(run, state):
    # standard() verifies these files against state.standard_hashes before use.
    return read(inside(run, 'standard/production.json', True))


def mode_profile(config):
    mode = config['production']['selected_mode']
    return dict(config['platform']['modes'][mode], mode=mode)


def enrich_packet(packet, run, state):
    config = bundle(run, state)
    packet['schema_version'] = '0.2.0'
    packet['production'] = config
    return packet


def media_rows(artifacts):
    return [row for name in ('asset_media', 'board_media') for row in artifacts.get(name, {}).get('items', [])]


def resolve_references(keys, artifacts, run):
    available = {r.get('reference_key', r['item']): r for r in media_rows(artifacts)}
    require(len(keys) == len(set(keys)), 'duplicate reference keys')
    result = []
    for key in keys:
        require(key in available, f'missing accepted media reference: {key}')
        row = available[key]
        path = inside(run, row['file'], True)
        require(digest(path) == row['sha256'], f'reference hash mismatch: {key}')
        role = {'character': '人物外观与服装', 'space': '场景布局与光源', 'prop': '物品形制与状态', 'board': '镜序与构图参考'}[row['kind']]
        result.append({'reference_key': key, 'canonical_name': row['canonical_name'],
                       'file': row['file'], 'sha256': row['sha256'], 'media_revision': row['revision'],
                       'planned_slot': len(result)+1, 'role': role})
    return result


def queue(row, artifacts, config):
    source = artifacts[row['fanout']['source']]
    mode = row['fanout']['mode']
    if mode == 'media_requirements':
        rows = []
        for asset in source['items']:
            for requirement in asset['media_requirements']:
                require(requirement['coverage_policy'] == 'independent', 'scene_reference coverage not implemented; use independent media')
                # Optional references are not silently generated.
                if not requirement['required']:
                    continue
                rows.append({'item': requirement['reference_key'], 'kind': asset['kind'], 'asset': asset,
                             **requirement, 'size': row['fanout']['size_by_kind'][asset['kind']]})
        return rows
    if mode == 'per_board':
        return [dict(board, item=board['board_id'], kind='board', size=row['fanout']['default_size']) for board in source['boards']]
    if mode == 'per_segment':
        return [{'item': 'PROMPT-' + segment['video_id'], 'kind': 'video_prompt', 'segment': segment,
                 'video_id': segment['video_id'], 'size': ''} for segment in source['segments']]
    raise ValueError('unknown production fanout mode: ' + mode)


def slice_packet(row, spec, artifacts, run, config):
    """Only the current board/segment, consumed assets and continuity context."""
    result = {key: deepcopy(value) for key, value in artifacts.items() if key in row['inputs']}
    refs = []
    if row['fanout']['mode'] in ('per_board', 'per_segment'):
        plan = artifacts['production_plan']
        if 'segment' in spec:
            segment = spec['segment']
            boards = [b for b in plan['boards'] if b['video_id'] == segment['video_id']]
            spans = segment['source_spans']
            keys = list(segment['reference_keys']) + [b['board_id'] for b in boards]
        else:
            boards = [spec]
            segment = next(s for s in plan['segments'] if s['video_id'] == spec['video_id'])
            span_ids = {panel['span_id'] for panel in spec['panels']}
            spans = [s for s in segment['source_spans'] if s['span_id'] in span_ids]
            keys = list(spec['reference_keys'])
        keys = list(dict.fromkeys(keys))
        refs = resolve_references(keys, artifacts, run)
        require(len(refs) <= mode_profile(config)['max_images'], 'reference images exceed selected platform capacity')
        shots = {s['shot_id'] for s in spans}
        result['storyboard'] = dict(artifacts['storyboard'], items=[s for s in artifacts['storyboard']['items'] if s['id'] in shots])
        used_assets = {r['reference_key'] for r in refs}
        result['assets'] = dict(artifacts['assets'], items=[a for a in artifacts['assets']['items']
                              if any(m['reference_key'] in used_assets for m in a['media_requirements'])])
        for name in ('asset_media', 'board_media'):
            if name in result:
                result[name] = dict(artifacts[name], items=[r for r in artifacts[name]['items'] if r.get('reference_key', r['item']) in used_assets])
        if 'edit_sound' in result:
            result['edit_sound'] = dict(artifacts['edit_sound'], items=[r for r in artifacts['edit_sound']['items'] if r['shot_id'] in shots])
        result['production_plan'] = {'schema_version': '0.2.0', 'type': 'production_plan', 'segments': [segment], 'boards': boards}
    else:
        result['assets'] = spec['asset']
    return result, refs


def check_artifact(candidate, kind, inputs, config):
    from .registry import registry_check, storyboard_check, story_check
    if kind == 'story':
        story_check(candidate, inputs)
    elif kind == 'storyboard':
        storyboard_check(candidate, inputs)
    elif kind == 'assets':
        registry_check(candidate, shot_ids=[s['id'] for s in inputs['storyboard']['items']])
        # Every binding must resolve to an explicit identity and state.
        assets = {a['id']: a for a in candidate['items']}
        for shot in inputs['storyboard']['items']:
            for bind in shot['asset_bindings']:
                require(bind['asset_id'] in assets, f"unknown asset binding in {shot['id']}")
                states = {s['state_id']:s for s in assets[bind['asset_id']]['states']}
                require(bind['state_id'] in states and shot['id'] in states[bind['state_id']]['shot_ids'], 'asset state binding mismatch')
                require(any(r['required'] and r['state_id'] == bind['state_id'] for r in assets[bind['asset_id']]['media_requirements']), 'bound asset state requires a reference image')
    elif kind == 'production_plan':
        from .production_plan import validate_production_plan
        storyboard = bound_storyboard(inputs['storyboard'], inputs['assets'])
        validate_production_plan(candidate, storyboard, mode_profile(config), max_panels=config['production']['board_max_panels'])
        require(candidate.get('items') == [dict(s, id=s['video_id']) for s in candidate['segments']], 'production_plan review items must mirror segments')
        known = {m['reference_key'] for a in inputs['assets']['items'] for m in a['media_requirements'] if m['required']}
        for segment in candidate['segments']:
            require(set(segment['reference_keys']) <= known, 'plan contains unknown reference key')
    else:
        artifact_check(candidate, kind, inputs)


def bound_storyboard(storyboard, assets):
    """Derive references from accepted identities/states, never free-form names."""
    result = deepcopy(storyboard)
    known = {a['id']: a for a in assets['items']}
    for shot in result['items']:
        refs = []
        for binding in shot['asset_bindings']:
            require(binding['asset_id'] in known, f"unknown asset in {shot['id']}")
            asset = known[binding['asset_id']]
            refs.extend(r['reference_key'] for r in asset['media_requirements']
                        if r['state_id'] == binding['state_id'] and r['required'])
        shot['reference_keys'] = list(dict.fromkeys(refs))
    return result


def accept_item(candidate, task, run):
    from .media import inspect_image
    from .registry import canonical_filename
    spec = task['fanout']['spec']
    if task['artifact_type'] == 'video_prompt':
        from .prompts import validate_and_render
        normalized = validate_and_render(candidate, dict(spec, references=task['fanout']['references']), mode_profile(task['production']))
        return dict(normalized, consumed_refs=task['fanout']['references'])
    media_item_check(candidate)
    require(candidate['item'] == spec['item'] and candidate['file'] == task['fanout']['target_file'], 'candidate media target mismatch')
    details = inspect_image(run, candidate)
    expected_w, expected_h = map(int, spec['size'].split('x'))
    require((details['width'], details['height']) == (expected_w, expected_h), 'image dimensions differ from task size')
    revision = task['fanout']['revision']
    if spec['kind'] == 'board':
        name = spec['item'] + f'_r{revision:03d}'
        identity = {'board_id': spec['item'], 'reference_key': spec['item']}
    else:
        asset = spec['asset']
        name = Path(canonical_filename(asset['id'], asset['display_name'], spec['state_id'], spec['view'], revision)).stem
        identity = {'asset_id': asset['id'], 'state_id': spec['state_id'], 'view': spec['view'], 'reference_key': spec['reference_key']}
    return dict(candidate, **details, **identity, kind=spec['kind'], revision=revision, canonical_name=name,
                consumed_refs=task['fanout']['references'])
