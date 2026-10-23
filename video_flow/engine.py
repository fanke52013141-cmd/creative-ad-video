"""Versioned task protocol and local acceptance engine.

Codex owns actual subagent spawning. dispatch produces a bounded task, bind records
the actual agent ID, and submit validates its receipt; no printed task is execution.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import shutil
import uuid
import yaml
from .contracts import FlowError, require, brief_check, artifact_check, review_check, text
from .storage import read, write, digest, tree_digest, inside, transaction

ROOT = Path(__file__).resolve().parents[1]


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


def initialize(run, brief, approval='key_decisions', root=ROOT):
    run, root = Path(run).resolve(), Path(root).resolve()
    require(approval in {'key_decisions', 'automatic'}, 'unknown approval policy')
    workflow = load_yaml(root / 'config/workflow.yaml')
    graph_check(workflow)
    routes = load_yaml(root / 'config/routes.yaml')
    route = resolve_route(brief, routes)
    require(not run.exists(), 'run directory already exists')
    skills = {route['writer'] if x['skill'] == '$writer' else x['skill'] for x in workflow['stages']}
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
        write(tmp / 'inputs/brief.json', brief)
        write(tmp / 'inputs/route.json', route)
        state = {'version': '0.1.0', 'run_id': uuid.uuid4().hex, 'sequence': 0,
                 'approval_policy': approval, 'delivery_level': workflow['delivery_level'],
                 'standard_hashes': {name: digest(tmp / 'standard' / name) for name in
                                     ('workflow.json', 'routes.json', 'skills.lock.json')},
                 'artifacts': {key: {'path': f'inputs/{key}.json', 'sha256': digest(tmp / f'inputs/{key}.json'), 'revision': 1}
                               for key in ('brief', 'route')},
                 'stages': {row['id']: {'status': 'pending', 'attempts': 0, 'task_id': None} for row in workflow['stages']},
                 'tasks': {}, 'history': [], 'events': []}
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


def ready_rows(workflow, state):
    rows = []
    for row in workflow['stages']:
        if state['stages'][row['id']]['status'] != 'pending':
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
    return {'run_id': state['run_id'], 'sequence': state['sequence'], 'stages': state['stages'],
            'ready': [x['id'] for x in ready_rows(workflow, state)]}


def event(state, action, **fields):
    state['events'].append({'time': datetime.now(timezone.utc).isoformat(), 'action': action, **fields})


def dispatch(run, stage):
    run = Path(run)
    with transaction(run) as state:
        integrity(run, state)
        workflow = standard(run, state)
        rows = {x['id']: x for x in ready_rows(workflow, state)}
        require(stage in rows, f'stage not ready: {stage}')
        row = rows[stage]
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
        # Revision repair receives only the previous review, never unrelated history.
        if not row.get('reviews'):
            feedback = state['stages'][stage].get('feedback')
            if feedback:
                path = inside(run, feedback['path'], True)
                require(digest(path) == feedback['sha256'], 'feedback hash mismatch')
                packet['repair_feedback'] = read(path)
        packet['input_hashes'] = {k: v['sha256'] for k, v in packet['input_refs'].items()}
        path = run / 'tasks' / (task_id + '.json')
        write(path, packet)
        (run / 'work' / task_id).mkdir(parents=True)
        state['tasks'][task_id] = {'path': path.relative_to(run).as_posix(), 'sha256': digest(path), 'agent_id': None, 'status': 'dispatched'}
        state['stages'][stage].update(status='dispatched', task_id=task_id)
        state['stages'][stage]['attempts'] += 1
        event(state, 'dispatch', stage=stage, task_id=task_id)
    return packet


def task_load(run, state, task_id):
    require(task_id in state['tasks'], 'unknown task')
    entry = state['tasks'][task_id]
    path = inside(run, entry['path'], True)
    require(digest(path) == entry['sha256'], 'task packet hash mismatch')
    task = read(path)
    require(state['stages'][task['stage']]['task_id'] == task_id, 'stale task')
    return entry, task


def bind(run, task_id, agent_id):
    require(text(agent_id), 'agent id required')
    with transaction(run) as state:
        integrity(run, state)
        entry, task = task_load(run, state, task_id)
        require(entry['status'] == 'dispatched' and entry['agent_id'] is None, 'task already bound or closed')
        if task['review_target']:
            target_task = state['stages'][task['review_target']]['task_id']
            require(state['tasks'][target_task]['agent_id'] != agent_id, 'reviewer must differ from author')
        entry['agent_id'] = agent_id
        entry['status'] = 'running'
        state['stages'][task['stage']]['status'] = 'running'
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
        if key in state['artifacts']:
            state['history'].append({'stage': key, **state['artifacts'].pop(key)})
        row.update(status='pending', task_id=None)
        row.pop('approval', None)
    event(state, 'invalidate', stage=stage, reason=reason)


def invalidate(run, stage, reason):
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
            require(state['artifacts'].get(key) == ref, 'input revision changed')
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
        if row.get('reviews'):
            target = row['reviews']
            review_check(candidate, task['inputs'][target], task['input_hashes'][target], row['criteria'])
        else:
            artifact_check(candidate, row['artifact_type'], task['inputs'])
        revision = 1 + sum(x['stage'] == row['id'] for x in state['history'])
        dest = run / 'artifacts' / row['id'] / f'{revision}-{task_id}.json'
        receipt_dest = dest.with_name(dest.stem + '-receipt.json')
        write(dest, candidate)
        write(receipt_dest, receipt)
        ref = {'path': dest.relative_to(run).as_posix(), 'sha256': digest(dest), 'revision': revision}
        state['artifacts'][row['id']] = ref
        entry.update(status='submitted', receipt_path=receipt_dest.relative_to(run).as_posix(), receipt_sha256=digest(receipt_dest))
        state['stages'][row['id']]['status'] = 'submitted'
        if row.get('reviews'):
            if candidate['verdict'] == 'revise':
                invalidate_state(state, workflow, target, 'independent review requested revision')
                state['stages'][target]['feedback'] = ref
            else:
                needs_approval = row.get('human_gate') and state['approval_policy'] == 'key_decisions'
                state['stages'][row['id']]['status'] = 'awaiting_approval' if needs_approval else 'accepted'
                state['stages'][target]['status'] = 'quality_passed' if needs_approval else 'accepted'
        event(state, 'submit', task_id=task_id, sha256=ref['sha256'])
    return status(run)


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
        state['stages'][row['id']].update(status='pending', task_id=None)
        event(state, 'retry', task_id=task_id, reason=reason)
    return status(run)


def package(run):
    run = Path(run)
    with transaction(run) as state:
        integrity(run, state)
        require(all(row['status'] == 'accepted' for row in state['stages'].values()), 'all stages must be accepted before delivery')
        for task_id, entry in state['tasks'].items():
            if entry['status'] == 'stale':
                continue
            task_load(run, state, task_id)
            require(entry.get('receipt_path') and digest(inside(run, entry['receipt_path'], True)) == entry['receipt_sha256'], 'receipt integrity mismatch')
        pkg_id = 'PKG-' + uuid.uuid4().hex
        base = run / 'packages' / pkg_id
        files = []
        for name, ref in state['artifacts'].items():
            source = inside(run, ref['path'], True)
            dest = base / (name + '.json')
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            require(digest(dest) == ref['sha256'], 'package copy hash mismatch')
            files.append({'artifact': name, 'path': dest.name, 'sha256': digest(dest), 'size': dest.stat().st_size})
        manifest = {'delivery_level': state['delivery_level'], 'run_id': state['run_id'],
                    'files': files, 'enforcement_level': 'acceptance',
                    'limitations': ['Text preproduction only; no generated media.', 'Local actor IDs are audit labels, not authenticated identities.']}
        write(base / 'manifest.json', manifest)
        event(state, 'package', package_id=pkg_id, manifest_sha256=digest(base / 'manifest.json'))
    return {'package': str(base.resolve()), 'manifest': manifest}


def bindable_prompt(packet):
    return (f"Read task packet and its locked skill at {packet['skill_path']}. "
            f"Task ID {packet['task_id']}; output only candidate.json and receipt.json in {packet['output_root']}. "
            "Use fresh context, the supplied inputs and applicable skill reference sections. "
            "The coordinator will bind your actual agent ID. Return needs_input rather than invent facts. "
            "Do not submit, approve, modify checkpoint, or read unrelated run artifacts.")
