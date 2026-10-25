"""Versioned task protocol and local acceptance engine.

Codex owns actual subagent spawning. dispatch produces a bounded task, bind records
the actual agent ID, and submit validates its receipt; no printed task is execution.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import uuid
import yaml
from .contracts import (FlowError, require, brief_check, artifact_check, review_check, text,
                        media_item_check, media_check, fanout_set_check, video_prompt_check)
from .storage import read, write, digest, tree_digest, inside, transaction

ROOT = Path(__file__).resolve().parents[1]
GENESIS = 'GENESIS'


def event_digest(ev):
    body = {k: v for k, v in ev.items() if k != 'digest'}
    payload = json.dumps(body, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def event(state, action, **fields):
    prev = state['events'][-1]['digest'] if state['events'] and 'digest' in state['events'][-1] else GENESIS
    ev = {'time': datetime.now(timezone.utc).isoformat(), 'action': action, 'seq': len(state['events']), 'prev': prev, **fields}
    ev['digest'] = event_digest(ev)
    state['events'].append(ev)


def verify_events(state):
    """Hash-chained history: any edit or reordering of persisted events breaks the chain.

    Runs created before chaining have unchained prefixes; they verify only until the
    first chained event, after which chaining is mandatory.
    """
    prev = GENESIS
    chained = False
    for i, ev in enumerate(state['events']):
        if 'digest' not in ev:
            require(not chained, f'event chain broken at {i}: unchained event after chained history')
            continue
        chained = True
        require(ev.get('prev') == prev and ev.get('seq') == i, f'event chain broken at {i}')
        require(event_digest(ev) == ev['digest'], f'event digest mismatch at {i}')
        prev = ev['digest']


def load_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding='utf-8-sig'))


def resolve_route(brief, routes):
    brief_check(brief)
    require(brief['style'] in routes['supported_styles'], 'unsupported style')
    for rule in routes['rules']:
        conditions = rule['when']
        match = all(
            brief['episode_count'] >= val if key == 'episode_count_min'
            else brief['goal'] in val if key == 'goal_in'
            else brief.get(key) == val
            for key, val in conditions.items()
        )
        if match:
            require(rule['supported'], rule.get('reason', 'unsupported route'))
            return {'type': 'route', 'rule_id': rule['id'], 'writer': rule['writer'],
                    'style': brief['style'], 'evidence': {key: brief[key] for key in
                    ('goal', 'narrative_form', 'episode_count', 'distribution', 'style')},
                    'constraints': brief['constraints']}
    raise FlowError('unsupported route: no matching supported capability')


def graph_check(workflow):
    rows = workflow['stages']
    seen = set()
    ancestors = {}
    for row in rows:
        require(row['id'] not in seen, 'duplicate stage')
        require(set(row['depends_on']) <= seen, 'stages must be acyclic and topologically ordered')
        require(set(row['inputs']) <= seen | {'brief', 'route'}, 'input has no producer')
        closure = set(row['depends_on'])
        for dependency in row['depends_on']:
            closure.update(ancestors[dependency])
        require(set(row['inputs']) - {'brief', 'route'} <= closure, 'input producer is not a declared ancestor')
        if row.get('reviews'):
            require(row['reviews'] in row['depends_on'], 'review target must be a dependency')
            require(row.get('criteria') and len(row['criteria']) == len(set(row['criteria'])), 'review needs unique criteria')
        seen.add(row['id'])
        ancestors[row['id']] = closure
    generators = {x['id'] for x in rows if not x.get('reviews')}
    targets = [x['reviews'] for x in rows if x.get('reviews')]
    require(generators == set(targets) and len(targets) == len(set(targets)), 'each generator needs exactly one review')


def initialize(run, brief, approval='key_decisions', root=ROOT, media=False, production_config=None):
    run, root = Path(run).resolve(), Path(root).resolve()
    require(approval in {'key_decisions', 'automatic'}, 'unknown approval policy')
    workflow = load_yaml(root / 'config/workflow.yaml')
    from .production_runtime import materialize_workflow
    production = None
    if production_config is not None:
        from .profiles import load_production_bundle
        require(media, 'production config requires --media')
        production = load_production_bundle(production_config)
    workflow = materialize_workflow(workflow, production is not None)
    if production:
        workflow['repair_limit'] = production['production']['repair_limit']
    elif media:
        workflow = dict(workflow, delivery_level=workflow.get('delivery_level_media', 'preproduction_text_and_reference_media'))
    else:
        workflow = dict(workflow, stages=[row for row in workflow['stages'] if not row.get('media')])
    graph_check(workflow)
    routes = load_yaml(root / 'config/routes.yaml')
    route = resolve_route(brief, routes)
    require(not run.exists(), 'run directory already exists')
    skills = {route['writer'] if x['skill'] == '$writer' else x['skill'] for x in workflow['stages']}
    for x in workflow['stages']:
        skills.update((x.get('fanout') or {}).get('skill_by_kind', {}).values())
    for skill in skills:
        require((root / '.agents/skills' / skill / 'SKILL.md').is_file(), f'missing skill: {skill}')
    # Build in a sibling temp directory, making incomplete initialization invisible.
    tmp = run.with_name(run.name + '.init-' + uuid.uuid4().hex)
    try:
        tmp.mkdir(parents=True)
        lock = {}
        for skill in sorted(skills):
            source = root / '.agents/skills' / skill
            tree_digest(source)  # reject symlinks before copying
            dest = tmp / 'standard/skills' / skill
            shutil.copytree(source, dest)
            lock[skill] = tree_digest(dest)
        write(tmp / 'standard/workflow.json', workflow)
        write(tmp / 'standard/routes.json', routes)
        write(tmp / 'standard/skills.lock.json', lock)
        if production:
            write(tmp / 'standard/production.json', production)
        write(tmp / 'inputs/brief.json', brief)
        write(tmp / 'inputs/route.json', route)
        state = {'version': '0.2.0' if production else '0.1.0', 'run_id': uuid.uuid4().hex, 'sequence': 0,
                 'approval_policy': approval, 'delivery_level': workflow['delivery_level'],
                 'standard_hashes': {name: digest(tmp / 'standard' / name) for name in
                                     ('workflow.json', 'routes.json', 'skills.lock.json')},
                 'artifacts': {key: {'path': f'inputs/{key}.json', 'sha256': digest(tmp / f'inputs/{key}.json'), 'revision': 1}
                               for key in ('brief', 'route')},
                 'stages': {row['id']: {'status': 'pending', 'attempts': 0, 'task_id': None} for row in workflow['stages']},
                 'tasks': {}, 'history': [], 'events': []}
        if production:
            state['standard_hashes']['production.json'] = digest(tmp / 'standard/production.json')
        write(tmp / 'checkpoint.json', state)
        tmp.rename(run)
    except BaseException:
        if tmp.exists():
            shutil.rmtree(tmp)  # path is the freshly created, named sibling only
        raise
    return {'run': str(run), 'route': route}


def standard(run, state):
    for name, expected in state['standard_hashes'].items():
        require(digest(inside(run, 'standard/' + name, True)) == expected, 'run standard changed')
    return read(Path(run) / 'standard/workflow.json')


def artifact(run, state, name):
    require(name in state['artifacts'], f'missing artifact {name}')
    ref = state['artifacts'][name]
    path = inside(run, ref['path'], True)
    require(digest(path) == ref['sha256'], f'artifact hash mismatch: {name}')
    return read(path)


def integrity(run, state):
    standard(run, state)
    for name in state['artifacts']:
        artifact(run, state, name)
    verify_events(state)
    if state.get('story_source'):
        ref = state['story_source']
        require(digest(inside(run, ref['path'], True)) == ref['sha256'], 'imported story source changed')


def task_roles(run, state):
    """Agent ids split by role across the whole run, from the bound task packets."""
    authors, reviewers = set(), set()
    for entry in state['tasks'].values():
        if entry.get('agent_id') is None:
            continue
        task = read(inside(run, entry['path'], True))
        (reviewers if task.get('review_target') else authors).add(entry['agent_id'])
    return authors, reviewers


def ready_rows(workflow, state):
    rows = []
    for row in workflow['stages']:
        entry = state['stages'][row['id']]
        if row.get('fanout'):
            if entry['status'] not in ('pending', 'in_progress'):
                continue
        elif entry['status'] != 'pending':
            continue
        def available(dep):
            status = state['stages'][dep]['status']
            return status == 'submitted' if row.get('reviews') == dep else status == 'accepted'
        if all(available(dep) for dep in row['depends_on']):
            rows.append(row)
    return rows


def status(run):
    state = read(Path(run) / 'checkpoint.json')
    integrity(run, state)
    workflow = standard(run, state)
    stages = {}
    for key, entry in state['stages'].items():
        row = stages[key] = dict(entry)
        if 'item_states' in entry:
            row['items_pending'] = sorted(k for k, v in entry['item_states'].items() if v['status'] != 'done')
            row['items_done'] = sorted(k for k, v in entry['item_states'].items() if v['status'] == 'done')
            row.pop('item_states', None)
            row.pop('results', None)
    return {'run_id': state['run_id'], 'sequence': state['sequence'], 'stages': stages,
            'ready': [x['id'] for x in ready_rows(workflow, state)]}


def fanout_queue(run, state, row):
    """Item queue for a fanout stage, derived from its locked source artifact."""
    spec = row['fanout']
    if state.get('version') == '0.2.0':
        from .production_runtime import queue, bundle
        data = {name: artifact(run, state, name) for name in row['inputs']}
        return queue(row, data, bundle(run, state))
    data = artifact(run, state, spec['source'])
    if spec.get('mode') == 'per_shot':
        # Full shot record rides along: the prompt worker must see its own shot's fields.
        return [{'item': 'PROMPT-' + it['id'], 'kind': 'video_prompt', 'shot_id': it['id'],
                 'shot': it, 'size': ''} for it in data['items']]
    if spec['source'] == 'assets':
        kinds = set(spec.get('select_kinds', []))
        flag = spec.get('reference_flag')
        chosen = [it for it in data['items'] if it.get('kind') in kinds or (flag and it.get(flag) is True)]
        sizes = spec.get('size_by_kind', {})
        rows = []
        for it in chosen:
            q = {k: v for k, v in it.items() if k != 'id'}  # full record: anchors/rules ride along
            q['item'] = it['id']
            q['kind'] = it.get('kind', '')
            q['size'] = sizes.get(it.get('kind'), spec.get('default_size', '1024x1024'))
            rows.append(q)
        return rows
    if spec['source'] == 'storyboard':
        groups = {}
        for it in data['items']:
            groups.setdefault(it['scene_id'], []).append(it)
        size = spec.get('default_size', '1280x720')
        return [{'item': 'BOARD-' + scene, 'kind': 'board', 'scene_id': scene, 'shots': shots, 'size': size}
                for scene, shots in sorted(groups.items())]
    raise FlowError('unsupported fanout source: ' + str(spec['source']))


def dispatch(run, stage, item=None, executor_type='agent'):
    run = Path(run)
    with transaction(run) as state:
        integrity(run, state)
        workflow = standard(run, state)
        rows = {x['id']: x for x in ready_rows(workflow, state)}
        require(stage in rows, f'stage not ready: {stage}')
        row = rows[stage]
        require(executor_type in ('agent', 'import'), 'unknown executor type')
        require(executor_type == 'agent' or (state.get('version') == '0.2.0' and row.get('fanout') and row.get('item_artifact', 'media_item') == 'media_item'), 'import executor requires v0.2 media item')
        if row.get('fanout'):
            return dispatch_item(run, state, workflow, row, item, executor_type)
        require(state['stages'][stage]['attempts'] <= workflow['repair_limit'], 'repair budget exhausted')
        route = artifact(run, state, 'route')
        skill = route['writer'] if row['skill'] == '$writer' else row['skill']
        lock = read(run / 'standard/skills.lock.json')
        require(tree_digest(run / 'standard/skills' / skill) == lock[skill], 'skill hash mismatch')
        task_id = 'TASK-' + uuid.uuid4().hex
        packet = {'task_id': task_id, 'stage': stage, 'role': row['role'], 'skill': skill,
                  'skill_sha256': lock[skill], 'skill_path': str((run / 'standard/skills' / skill / 'SKILL.md').resolve()),
                  'artifact_type': row['artifact_type'], 'context_mode': 'fresh', 'inputs': {}, 'input_refs': {},
                  'output_root': str((run / 'work' / task_id).resolve()), 'review_target': row.get('reviews'),
                  'review_criteria': row.get('criteria', []),
                  'scope': 'Only write candidate.json and receipt.json under output_root; do not change checkpoint or accept/approve stages.'}
        for key in row['inputs']:
            packet['inputs'][key] = artifact(run, state, key)
            packet['input_refs'][key] = state['artifacts'][key].copy()
        if stage == 'story' and state.get('story_source'):
            ref = state['story_source'].copy()
            packet['inputs']['story_source'] = {'text': inside(run, ref['path'], True).read_text(encoding='utf-8'), **ref}
            packet['input_refs']['story_source'] = ref
        # Revision repair receives only the previous review, never unrelated history.
        if not row.get('reviews'):
            feedback = state['stages'][stage].get('feedback')
            if feedback:
                path = inside(run, feedback['path'], True)
                require(digest(path) == feedback['sha256'], 'feedback hash mismatch')
                packet['repair_feedback'] = read(path)
        packet['input_hashes'] = {k: v['sha256'] for k, v in packet['input_refs'].items()}
        if state.get('version') == '0.2.0':
            from .production_runtime import enrich_packet
            enrich_packet(packet, run, state)
        path = run / 'tasks' / (task_id + '.json')
        write(path, packet)
        (run / 'work' / task_id).mkdir(parents=True)
        state['tasks'][task_id] = {'path': path.relative_to(run).as_posix(), 'sha256': digest(path), 'agent_id': None, 'status': 'dispatched'}
        state['stages'][stage].update(status='dispatched', task_id=task_id)
        state['stages'][stage]['attempts'] += 1
        event(state, 'dispatch', stage=stage, task_id=task_id)
        return packet


def dispatch_item(run, state, workflow, row, item, executor_type='agent'):
    """One fanout item = one bounded task packet with only that item's content."""
    require(text(item), 'fanout stage requires an item id (see status items_pending)')
    entry = state['stages'][row['id']]
    if 'item_states' not in entry:
        queue = fanout_queue(run, state, row)
        require(queue, 'fanout source produced no items')
        entry['item_states'] = {q['item']: {'status': 'pending', 'attempts': 0, 'task_id': None} for q in queue}
        entry['results'] = {}
    require(item in entry['item_states'], 'unknown fanout item: ' + item)
    cell = entry['item_states'][item]
    require(cell['status'] == 'pending', 'item is not pending: ' + item)
    require(cell['attempts'] < workflow['repair_limit'] + 1, 'item repair budget exhausted: ' + item)
    queue = {q['item']: q for q in fanout_queue(run, state, row)}
    require(set(queue) == set(entry['item_states']), 'fanout source changed after queue was built')
    spec = queue[item]
    skill = row['fanout'].get('skill_by_kind', {}).get(spec['kind'], row['skill'])
    lock = read(run / 'standard/skills.lock.json')
    require(tree_digest(run / 'standard/skills' / skill) == lock[skill], 'skill hash mismatch')
    task_id = 'TASK-' + uuid.uuid4().hex
    fanout = {'item': item, 'kind': spec['kind']}
    if row.get('item_artifact', 'media_item') == 'media_item':
        fanout.update({'size': spec['size'], 'target_file': f"media/{row['id']}/{item}.png",
                       'profile': workflow.get('media_profile', {})})
    elif state.get('version') == '0.2.0':
        fanout['video_id'] = spec['video_id']
    else:
        fanout['shot_id'] = spec['shot_id']
    packet = {'task_id': task_id, 'stage': row['id'], 'role': row['role'], 'skill': skill,
              'skill_sha256': lock[skill], 'skill_path': str((run / 'standard/skills' / skill / 'SKILL.md').resolve()),
              'artifact_type': row.get('item_artifact', 'media_item'), 'context_mode': 'fresh', 'inputs': {}, 'input_refs': {},
              'output_root': str((run / 'work' / task_id).resolve()), 'review_target': None, 'review_criteria': [],
              'fanout': fanout,
              'scope': ('Generate exactly one image for this item at the target file; write only candidate.json and receipt.json under output_root.'
                        if 'target_file' in fanout else
                        'Write the text artifact for this single item; write only candidate.json and receipt.json under output_root.')}
    slice_rules = row['fanout'].get('slice_inputs') or {}
    for key in row['inputs']:
        if key == row['fanout']['source']:
            continue
        data = artifact(run, state, key)
        rule = slice_rules.get(key)
        if rule and 'shot' in spec:
            if rule['by'] == 'shot_id':
                one = next((x for x in data.get('items', []) if x.get('shot_id') == spec['shot_id']), None)
                require(one is not None, f"{key} has no entry for {spec['shot_id']}")
                packet['inputs'][key] = {'type': data.get('type'), 'items': [one]}
            elif rule['by'] == 'board_for_shot':
                board_id = 'BOARD-' + spec['shot'].get('scene_id', '')
                rows = [x for x in data.get('items', []) if x.get('item') == board_id]
                require(rows, f"{key} has no entry for {board_id}")
                packet['inputs'][key] = {'type': 'media', 'items': rows}
            else:
                raise FlowError('unknown slice rule: ' + rule['by'])
        else:
            packet['inputs'][key] = data
        packet['input_refs'][key] = state['artifacts'][key].copy()
    packet['input_refs'][row['fanout']['source']] = state['artifacts'][row['fanout']['source']].copy()
    packet['inputs'][row['fanout']['source']] = spec  # sliced single item, never the whole artifact
    if state.get('version') == '0.2.0':
        from .production_runtime import bundle, enrich_packet, slice_packet
        from .registry import canonical_filename, safe_name
        config = bundle(run, state)
        if row.get('item_artifact', 'media_item') == 'media_item' and executor_type == 'agent':
            require(config['production']['media_mode'] == 'mock', 'media requires import-media; automatic image provider is not registered')
        artifacts = {key: artifact(run, state, key) for key in row['inputs']}
        packet['inputs'], references = slice_packet(row, spec, artifacts, run, config)
        packet['fanout'].update(spec=spec, references=references, revision=cell['attempts']+1)
        packet['executor_type'] = executor_type
        packet['fanout']['profile'] = config['provider']
        packet['scope'] = ('Import exactly one supplied image; retain independent visual review.' if executor_type == 'import' else
                           'Execute only the locked mock media fixture; never invoke a paid provider.' if 'target_file' in fanout else
                           'Write the reference-bound video prompt for this segment; no video generation.')
        if 'target_file' in fanout:
            revision = cell['attempts']+1
            filename = (safe_name(item) + f'_r{revision:03d}.png' if spec['kind'] == 'board' else
                        canonical_filename(spec['asset']['id'], spec['asset']['display_name'], spec['state_id'], spec['view'], revision))
            packet['fanout']['target_file'] = f"media/{row['id']}/{task_id}/{filename}"
        enrich_packet(packet, run, state)
    feedback = entry.get('feedback')
    if feedback and cell['attempts'] > 0:
        path = inside(run, feedback['path'], True)
        require(digest(path) == feedback['sha256'], 'feedback hash mismatch')
        packet['repair_feedback'] = read(path)
    packet['input_hashes'] = {k: v['sha256'] for k, v in packet['input_refs'].items()}
    path = run / 'tasks' / (task_id + '.json')
    write(path, packet)
    (run / 'work' / task_id).mkdir(parents=True)
    state['tasks'][task_id] = {'path': path.relative_to(run).as_posix(), 'sha256': digest(path), 'agent_id': None, 'status': 'dispatched', 'item': item}
    cell.update(status='dispatched', task_id=task_id)
    cell['attempts'] += 1
    entry['status'] = 'in_progress'
    event(state, 'dispatch', stage=row['id'], task_id=task_id, item=item)
    return packet


def stage_owns_task(stage_entry, task_id):
    if 'item_states' in stage_entry:
        return any(cell.get('task_id') == task_id for cell in stage_entry['item_states'].values())
    return stage_entry.get('task_id') == task_id


def task_load(run, state, task_id):
    require(task_id in state['tasks'], 'unknown task')
    entry = state['tasks'][task_id]
    path = inside(run, entry['path'], True)
    require(digest(path) == entry['sha256'], 'task packet hash mismatch')
    task = read(path)
    require(stage_owns_task(state['stages'][task['stage']], task_id), 'stale task')
    return entry, task


def bind(run, task_id, agent_id):
    require(text(agent_id), 'agent id required')
    with transaction(run) as state:
        integrity(run, state)
        entry, task = task_load(run, state, task_id)
        if task.get('executor_type') == 'import':
            require(agent_id == 'import:' + task_id, 'import task must bind its actual deterministic operation identity')
        else:
            require(not agent_id.startswith('import:'), 'import identity is reserved for import operations')
        require(entry['status'] == 'dispatched' and entry['agent_id'] is None, 'task already bound or closed')
        # Run-wide role isolation: no agent may review anything it (or its id) authored.
        authors, reviewers = task_roles(run, state)
        if task['review_target']:
            require(agent_id not in authors, 'reviewer must differ from any author of this run')
        else:
            require(agent_id not in reviewers, 'author id must not already be a reviewer of this run')
        entry['agent_id'] = agent_id
        entry['status'] = 'running'
        stage = state['stages'][task['stage']]
        if 'item_states' in stage:
            stage['item_states'][entry['item']]['status'] = 'running'
        else:
            stage['status'] = 'running'
        event(state, 'bind', task_id=task_id, agent_id=agent_id)
    return {'task_id': task_id, 'agent_id': agent_id}


def descendants(workflow, stage):
    found = {stage}
    for row in workflow['stages']:
        if set(row['depends_on']) & found or set(row['inputs']) & found:
            found.add(row['id'])
    return found


def invalidate_state(state, workflow, stage, reason):
    for key in descendants(workflow, stage):
        row = state['stages'][key]
        if row.get('task_id'):
            state['tasks'][row['task_id']]['status'] = 'stale'
        for cell in row.get('item_states', {}).values():
            if cell.get('task_id'):
                state['tasks'][cell['task_id']]['status'] = 'stale'
        if key in state['artifacts']:
            state['history'].append({'stage': key, **state['artifacts'].pop(key)})
        row.update(status='pending', task_id=None)
        row.pop('approval', None)
        row.pop('item_states', None)
        row.pop('results', None)
        row.pop('feedback', None)
    event(state, 'invalidate', stage=stage, reason=reason)


def invalidate_item(run, stage, item, reason):
    """Reopen exactly one fanout item; its siblings keep their accepted results."""
    require(text(reason), 'invalidation reason required')
    with transaction(run) as state:
        workflow = standard(run, state)
        require(stage in state['stages'], 'unknown stage')
        row = next(x for x in workflow['stages'] if x['id'] == stage)
        require(row.get('fanout'), 'stage is not a fanout stage')
        entry = state['stages'][stage]
        require('item_states' in entry and item in entry['item_states'], 'unknown fanout item: ' + str(item))
        cell = entry['item_states'][item]
        if cell.get('task_id'):
            state['tasks'][cell['task_id']]['status'] = 'stale'
        entry['results'].pop(item, None)
        entry['item_states'][item] = {'status': 'pending', 'attempts': cell['attempts'], 'task_id': None}
        if stage in state['artifacts']:
            state['history'].append({'stage': stage, **state['artifacts'].pop(stage)})
        entry['status'] = 'in_progress'
        invalidate_downstream(run, state, workflow, stage, {item})
        event(state, 'invalidate_item', stage=stage, item=item, reason=reason)
    return status(run)


def invalidate(run, stage, reason, item=None):
    if item is not None:
        return invalidate_item(run, stage, item, reason)
    require(text(reason), 'invalidation reason required')
    with transaction(run) as state:
        workflow = standard(run, state)
        require(stage in state['stages'], 'unknown stage')
        row = next(x for x in workflow['stages'] if x['id'] == stage)
        # Invalidating a review must reopen its target, not leave an accepted source orphaned.
        origin = row.get('reviews', stage)
        invalidate_state(state, workflow, origin, reason)
    return {'invalidated_from': origin}


def submit(run, task_id):
    run = Path(run)
    with transaction(run) as state:
        integrity(run, state)
        workflow = standard(run, state)
        entry, task = task_load(run, state, task_id)
        require(entry['status'] == 'running' and entry['agent_id'], 'task must be bound and running')
        lock = read(run / 'standard/skills.lock.json')
        require(tree_digest(run / 'standard/skills' / task['skill']) == lock[task['skill']], 'skill changed after dispatch')
        for key, ref in task['input_refs'].items():
            current = state.get('story_source') if key == 'story_source' else state['artifacts'].get(key)
            require(current == ref, 'input revision changed')
        base = run / 'work' / task_id
        path = inside(base, 'candidate.json', True)
        receipt_path = inside(base, 'receipt.json', True)
        candidate, receipt = read(path), read(receipt_path)
        require(isinstance(candidate, dict) and isinstance(receipt, dict), 'candidate and receipt must be objects')
        require(candidate.get('task_id') == task_id, 'candidate task mismatch')
        require(receipt.get('task_id') == task_id and receipt.get('agent_id') == entry['agent_id'], 'receipt actor/task mismatch')
        require(receipt.get('skill_sha256') == task['skill_sha256'], 'receipt skill mismatch')
        require(receipt.get('input_hashes') == task['input_hashes'], 'receipt inputs mismatch')
        require(receipt.get('output_sha256') == digest(path), 'receipt output hash mismatch')
        row = next(x for x in workflow['stages'] if x['id'] == task['stage'])
        normalized_item = None
        if row.get('reviews'):
            target = row['reviews']
            review_check(candidate, task['inputs'][target], task['input_hashes'][target], row['criteria'])
            if state.get('version') == '0.2.0':
                for issue in candidate['issues']:
                    if 'target_ids' in issue:
                        require(isinstance(issue['target_ids'], list) and all(text(x) for x in issue['target_ids']), 'target_ids must be a string array')
        elif state.get('version') == '0.2.0':
            from .production_runtime import accept_item, check_artifact, bundle
            require(candidate.get('schema_version') == '0.2.0', 'candidate schema_version must be 0.2.0')
            if row.get('fanout'):
                normalized_item = accept_item(candidate, task, run)
            else:
                check_artifact(candidate, row['artifact_type'], task['inputs'], bundle(run, state))
        elif row.get('fanout') and row.get('item_artifact', 'media_item') == 'media_item':
            media_item_check(candidate)
            require(candidate['item'] == task['fanout']['item'], 'candidate item mismatch')
            require(candidate['file'] == task['fanout']['target_file'], 'candidate file must be the packet target file')
            media_path = inside(run, candidate['file'], True)
            require(digest(media_path) == candidate['sha256'], 'media file hash mismatch')
        elif row.get('fanout'):
            video_prompt_check(candidate)
            require(candidate['item'] == task['fanout']['item'], 'candidate item mismatch')
            require(candidate['shot_id'] == task['fanout']['shot_id'], 'candidate shot mismatch')
        else:
            artifact_check(candidate, row['artifact_type'], task['inputs'])
        revision = 1 + sum(x['stage'] == row['id'] for x in state['history'])
        dest = run / 'artifacts' / row['id'] / f'{revision}-{task_id}.json'
        receipt_dest = dest.with_name(dest.stem + '-receipt.json')
        write(dest, candidate)
        write(receipt_dest, receipt)
        ref = {'path': dest.relative_to(run).as_posix(), 'sha256': digest(dest), 'revision': revision}
        entry.update(status='submitted', receipt_path=receipt_dest.relative_to(run).as_posix(), receipt_sha256=digest(receipt_dest))
        if row.get('fanout'):
            stage_entry = state['stages'][row['id']]
            item = task['fanout']['item']
            stage_entry['item_states'][item].update(status='done')
            if normalized_item is not None:
                stage_entry['results'][item] = normalized_item
            elif row.get('item_artifact', 'media_item') == 'media_item':
                stage_entry['results'][item] = {'item': item, 'kind': task['fanout']['kind'],
                                                'file': candidate['file'], 'sha256': candidate['sha256'],
                                                'prompt': candidate['prompt'], 'size': task['fanout']['size'],
                                                'model': candidate.get('model') or task['fanout']['profile'].get('model', ''),
                                                'quality': candidate.get('quality') or task['fanout']['profile'].get('quality', '')}
            else:
                stage_entry['results'][item] = dict(candidate)
            pending = [key for key, cell in stage_entry['item_states'].items() if cell['status'] != 'done']
            if not pending:
                if row.get('item_artifact', 'media_item') == 'media_item':
                    assembled = {'type': 'media', 'stage': row['id'], 'source': row['fanout']['source'],
                                 'profile': workflow.get('media_profile', {}),
                                 'items': [stage_entry['results'][key] for key in sorted(stage_entry['results'])]}
                    media_check(assembled, set(stage_entry['item_states']))
                else:
                    assembled = {'type': 'fanout_set', 'stage': row['id'], 'source': row['fanout']['source'],
                                 'items': [stage_entry['results'][key] for key in sorted(stage_entry['results'])]}
                    fanout_set_check(assembled, set(stage_entry['item_states']))
                revision_a = 1 + sum(x['stage'] == row['id'] for x in state['history'])
                dest_a = run / 'artifacts' / row['id'] / f'{revision_a}-assembled.json'
                write(dest_a, assembled)
                state['artifacts'][row['id']] = {'path': dest_a.relative_to(run).as_posix(),
                                                 'sha256': digest(dest_a), 'revision': revision_a}
                stage_entry['status'] = 'submitted'
                ref = state['artifacts'][row['id']]
        else:
            state['artifacts'][row['id']] = ref
            state['stages'][row['id']]['status'] = 'submitted'
        if row.get('reviews'):
            if candidate['verdict'] == 'revise':
                target_row = next(x for x in workflow['stages'] if x['id'] == target)
                if target_row.get('fanout'):
                    media_revise(state, workflow, target, ref, candidate, run)
                else:
                    invalidate_state(state, workflow, target, 'independent review requested revision')
                    state['stages'][target]['feedback'] = ref
            else:
                needs_approval = row.get('human_gate') and state['approval_policy'] == 'key_decisions'
                state['stages'][row['id']]['status'] = 'awaiting_approval' if needs_approval else 'accepted'
                state['stages'][target]['status'] = 'quality_passed' if needs_approval else 'accepted'
        event(state, 'submit', task_id=task_id, sha256=ref['sha256'])
    return status(run)


def media_revise(state, workflow, target, review_ref, review, run=None):
    """A revise on a fanout media artifact reopens only the items the review cites."""
    entry = state['stages'][target]
    require('item_states' in entry, 'media stage lost its item queue')
    if state.get('version') == '0.2.0':
        cited = {item for issue in review.get('issues', []) for item in issue.get('target_ids', [])}
        require(cited <= set(entry['item_states']), 'review cites unknown target_ids')
    else:
        cited = {item for item in entry['item_states']
                 if any(item in str(issue.get('location', '')) for issue in review.get('issues', []))}
    reset = cited or set(entry['item_states'])
    for item in reset:
        cell = entry['item_states'][item]
        if cell.get('task_id'):
            state['tasks'][cell['task_id']]['status'] = 'stale'
        entry['results'].pop(item, None)
        entry['item_states'][item] = {'status': 'pending', 'attempts': cell['attempts'], 'task_id': None}
    if target in state['artifacts']:
        state['history'].append({'stage': target, **state['artifacts'].pop(target)})
    entry['status'] = 'in_progress'
    entry['feedback'] = review_ref
    invalidate_downstream(run, state, workflow, target, reset)


def invalidate_downstream(run, state, workflow, origin, changed_keys):
    from .dependency_index import reset_stage, invalidate_dependents
    keys = descendants(workflow, origin) - {origin}
    if state.get('version') == '0.2.0' and run is not None:
        def reader(task_id):
            return read(inside(run, state['tasks'][task_id]['path'], True))
        return invalidate_dependents(state, workflow, origin, changed_keys, reader, keys)
    for key in keys:
        reset_stage(state, key)
    return {key: 'all' for key in keys}


def approve(run, stage, actor, reason):
    require(text(actor) and text(reason), 'approval requires actor and reason from user decision')
    with transaction(run) as state:
        integrity(run, state)
        row = next((x for x in standard(run, state)['stages'] if x['id'] == stage), None)
        require(row is not None and row.get('reviews'), 'approve requires a review stage')
        require(state['stages'][stage]['status'] == 'awaiting_approval', 'stage not awaiting approval')
        state['stages'][stage].update(status='accepted', approval={'actor': actor, 'reason': reason,
                     'artifact_sha256': state['artifacts'][row['reviews']]['sha256']})
        state['stages'][row['reviews']]['status'] = 'accepted'
        event(state, 'approve', stage=stage, actor=actor, reason=reason)
    return status(run)


def retry(run, task_id, reason):
    """Record a tool failure/needs-input without pretending a candidate was submitted."""
    require(text(reason), 'retry reason required')
    with transaction(run) as state:
        workflow = standard(run, state)
        entry, task = task_load(run, state, task_id)
        require(entry['status'] in {'running', 'dispatched'}, 'only active tasks can retry')
        row = next(x for x in workflow['stages'] if x['id'] == task['stage'])
        entry['status'] = 'stale'
        stage = state['stages'][row['id']]
        if 'item_states' in stage:
            cell = stage['item_states'][entry['item']]
            stage['item_states'][entry['item']] = {'status': 'pending', 'attempts': cell['attempts'], 'task_id': None}
            stage['status'] = 'in_progress'
        else:
            stage.update(status='pending', task_id=None)
        event(state, 'retry', task_id=task_id, reason=reason)
    return status(run)


def package(run, format=None, out=None):
    run = Path(run)
    with transaction(run) as state:
        integrity(run, state)
        require(all(row['status'] == 'accepted' for row in state['stages'].values()), 'all stages must be accepted before delivery')
        for task_id, entry in state['tasks'].items():
            if entry['status'] == 'stale':
                continue
            task_load(run, state, task_id)
            require(entry.get('receipt_path') and digest(inside(run, entry['receipt_path'], True)) == entry['receipt_sha256'], 'receipt integrity mismatch')
        if format == 'external-production' or (format is None and state.get('version') == '0.2.0'):
            require(state.get('version') == '0.2.0', 'external production export requires a v0.2 run')
            from .delivery import export_production_package
            from .production_runtime import bundle
            report = audit(run)
            require(report['status'] == 'clean', 'run audit failed: ' + '; '.join(report['violations']))
            artifacts = {name: artifact(run, state, name) for name in state['artifacts']}
            if out is None:
                (run / 'deliveries').mkdir(exist_ok=True)
                out = run / 'deliveries' / ('PKG-' + uuid.uuid4().hex)
            result = export_production_package(run, artifacts, out, bundle(run, state))
            manifest_path = Path(result['package']) / '_校验/manifest.json'
            event(state, 'package', package_id=Path(result['package']).name, manifest_sha256=digest(manifest_path))
            return result
        require(format in (None, 'audit'), 'unknown package format')
        require(out is None, '--out applies only to external-production packages')
        pkg_id = 'PKG-' + uuid.uuid4().hex
        base = run / 'packages' / pkg_id
        files = []
        has_media = False
        for name, ref in state['artifacts'].items():
            data = artifact(run, state, name)
            if data.get('type') == 'media':
                has_media = True
                for row in data['items']:
                    source = inside(run, row['file'], True)
                    require(digest(source) == row['sha256'], f"media hash mismatch: {row['item']}")
                    dest = base / row['file']
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, dest)
                    require(digest(dest) == row['sha256'], 'package copy hash mismatch')
                    files.append({'artifact': name, 'item': row['item'], 'path': row['file'],
                                  'sha256': row['sha256'], 'size': dest.stat().st_size})
            source = inside(run, ref['path'], True)
            dest = base / (name + '.json')
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            require(digest(dest) == ref['sha256'], 'package copy hash mismatch')
            files.append({'artifact': name, 'path': dest.name, 'sha256': digest(dest), 'size': dest.stat().st_size})
        limitations = (['Reference images generated via a host provider; no audio or video media yet.', 'Local actor IDs are audit labels, not authenticated identities.']
                       if has_media else
                       ['Text preproduction only; no generated media.', 'Local actor IDs are audit labels, not authenticated identities.'])
        manifest = {'delivery_level': state['delivery_level'], 'run_id': state['run_id'],
                    'files': files, 'enforcement_level': 'acceptance', 'limitations': limitations}
        write(base / 'manifest.json', manifest)
        event(state, 'package', package_id=pkg_id, manifest_sha256=digest(base / 'manifest.json'))
    return {'package': str(base.resolve()), 'manifest': manifest}


def preflight(run):
    state = read(Path(run) / 'checkpoint.json')
    integrity(run, state)
    require(state.get('version') == '0.2.0', 'preflight requires v0.2 production configuration')
    from .production_runtime import bundle
    config = bundle(run, state)
    issues = []
    if config['production']['media_mode'] == 'generate':
        issues.append('No automatic image provider adapter is registered; use import mode or configure a host adapter.')
    if not config['provider']['supports_reference_images']:
        issues.append('Image workflow requires a provider/import route with reference-image support.')
    return {'status': 'blocked' if issues else 'ready', 'issues': issues,
            'media_mode': config['production']['media_mode'], 'platform_profile_status': config['platform']['status'],
            'platform_binding': 'pending', 'external_video_result': 'unverified',
            'generation_invoked': False}


def validate(run, scope='delivery'):
    require(scope == 'delivery', 'unknown validation scope')
    state = read(Path(run) / 'checkpoint.json')
    integrity(run, state)
    require(all(row['status'] == 'accepted' for row in state['stages'].values()), 'all stages must be accepted before delivery')
    result = audit(run)
    require(result['status'] == 'clean', 'run audit failed: ' + '; '.join(result['violations']))
    return {'status': 'ready_for_export', 'scope': scope, 'audit': result}


def verify_package(path):
    from .delivery_validation import verify_package as verify
    return verify(path)


def import_media(run, reference_key, file, stage='asset_media'):
    from .imports import import_media as execute
    return execute(run, reference_key, file, stage)


def import_input(run, kind, file):
    from .imports import import_input as execute
    return execute(run, kind, file)


def bindable_prompt(packet):
    return (f"Read task packet and its locked skill at {packet['skill_path']}. "
            f"Task ID {packet['task_id']}; output only candidate.json and receipt.json in {packet['output_root']}. "
            "Use fresh context, the supplied inputs and applicable skill reference sections. "
            "The coordinator will bind your actual agent ID. Return needs_input rather than invent facts. "
            "Do not submit, approve, modify checkpoint, or read unrelated run artifacts.")


PROTOCOL = {
    'title': 'Video Flow 强制协调协议',
    'steps': [
        'init 创建 run（真实 run 置于仓库外）；不修改已初始化 run 的 brief 或标准。',
        'status 查看 ready；只 dispatch 就绪阶段（扇出阶段逐项 dispatch RUN STAGE ITEM）。',
        '以全新上下文 spawn 子 Agent：只传任务包、docs/contracts.md、锁定技能；主 Agent 不自己创作任何产物。',
        'bind 真实 agent ID 后告知工作者；工作者只写 candidate.json 与 receipt.json。',
        'submit 只验收候选；评审任务必须由与全部作者不同的全新 Agent 执行。',
        'revise 后按预算派修订轮（工作者只拿上一份评审）；耗尽预算即报告阻塞。',
        'awaiting_approval 由用户具体决定后 approve；automatic 模式仍保留独立质量评审。',
        '全部 accepted 后 package；交付前核对 manifest 哈希并如实声明限制。',
    ],
    'prohibited': [
        '主 Agent 直接创作 candidate 或代替子 Agent 生成媒体。',
        '作者复用为评审、编造 agent_id、伪造或补交回执。',
        '合并生成（一图多 item / 一包多镜）、修改锁定事实、绕过 CLI 直接改写 checkpoint。',
        '把合成测试通过宣称为创作质量，或宣称未执行的检查已执行。',
    ],
    'enforcement': 'acceptance',
}


def protocol():
    return dict(PROTOCOL)


def audit(run):
    """Forensic re-verification of a run: hashes, receipts, contract replay, role isolation, workdir hygiene.

    Acceptance-grade: detects misuse after the fact; it cannot prevent a full-privilege agent from tampering.
    """
    run = Path(run)
    violations = []
    checked = {'tasks': 0, 'stale_tasks': 0, 'artifacts': 0, 'media_files': 0}
    state = read(run / 'checkpoint.json')

    def flow_violation(label):
        violations.append(label)

    try:
        standard(run, state)
    except FlowError as exc:
        flow_violation(f'standard: {exc}')
    for name, ref in state['artifacts'].items():
        checked['artifacts'] += 1
        try:
            data = artifact(run, state, name)
            if data.get('type') == 'media':
                for row in data['items']:
                    checked['media_files'] += 1
                    if digest(inside(run, row['file'], True)) != row['sha256']:
                        flow_violation(f"media file hash mismatch: {row['item']}")
        except FlowError as exc:
            flow_violation(f'artifact {name}: {exc}')
    try:
        verify_events(state)
    except FlowError as exc:
        flow_violation(f'events: {exc}')

    workflow = read(run / 'standard/workflow.json')
    rows = {x['id']: x for x in workflow['stages']}
    authors, reviewers = set(), set()
    for task_id, entry in state['tasks'].items():
        try:
            task = read(inside(run, entry['path'], True))
        except FlowError as exc:
            flow_violation(f'task {task_id}: {exc}')
            continue
        if entry['status'] == 'stale':
            checked['stale_tasks'] += 1
            continue
        checked['tasks'] += 1
        role = 'reviewer' if task.get('review_target') else 'author'
        (reviewers if role == 'reviewer' else authors).add(entry.get('agent_id'))
        base = run / 'work' / task_id
        try:
            require(digest(inside(run, entry['path'], True)) == entry['sha256'], 'packet hash mismatch')
            receipt = read(inside(run, entry['receipt_path'], True))
            require(digest(inside(run, entry['receipt_path'], True)) == entry['receipt_sha256'], 'receipt file hash mismatch')
            require(receipt.get('task_id') == task_id and receipt.get('agent_id') == entry['agent_id'], 'receipt actor/task mismatch')
            candidate = read(base / 'candidate.json')
            require(receipt.get('output_sha256') == digest(base / 'candidate.json'), 'candidate hash mismatch')
            require(receipt.get('input_hashes') == task['input_hashes'], 'receipt inputs mismatch')
            require(receipt.get('skill_sha256') == task['skill_sha256'], 'receipt skill mismatch')
            extra = sorted(p.name for p in base.iterdir() if p.name not in {'candidate.json', 'receipt.json'})
            require(not extra, f'unexpected files in work dir: {", ".join(extra)}')
            row = rows[task['stage']]
            if task.get('review_target'):
                target_name = task['review_target']
                ref = state['artifacts'].get(target_name)
                require(ref is not None, 'missing review target artifact')
                review_check(candidate, read(inside(run, ref['path'], True)), task['input_hashes'][target_name], row['criteria'])
            elif row.get('fanout') and row.get('item_artifact', 'media_item') == 'media_item':
                if state.get('version') == '0.2.0':
                    from .production_runtime import accept_item
                    accept_item(candidate, task, run)
                else:
                    media_item_check(candidate)
                    require(candidate['file'] == task['fanout']['target_file'], 'candidate file mismatch')
                    require(digest(inside(run, candidate['file'], True)) == candidate['sha256'], 'media hash mismatch')
            elif row.get('fanout'):
                if state.get('version') == '0.2.0':
                    from .production_runtime import accept_item
                    accept_item(candidate, task, run)
                else:
                    video_prompt_check(candidate)
            else:
                if state.get('version') == '0.2.0':
                    from .production_runtime import check_artifact, bundle
                    check_artifact(candidate, row['artifact_type'], task['inputs'], bundle(run, state))
                else:
                    artifact_check(candidate, row['artifact_type'], task['inputs'])
        except FlowError as exc:
            flow_violation(f'task {task_id} ({role}): {exc}')
        except (OSError, KeyError, TypeError) as exc:
            flow_violation(f'task {task_id} ({role}): {exc}')
    crossing = reviewers & authors
    if crossing:
        flow_violation(f'role isolation: agent ids appear as both author and reviewer: {", ".join(sorted(crossing))}')

    return {'run': str(run.resolve()), 'run_id': state['run_id'], 'status': 'clean' if not violations else 'violations',
            'violations': violations, 'checked': checked}
