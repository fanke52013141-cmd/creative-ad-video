"""Invalidate consumed media identities without substring matching or stale work."""
from .contracts import require


def reset_stage(state, key):
    stage = state['stages'][key]
    task_ids = [stage.get('task_id')] + [c.get('task_id') for c in stage.get('item_states', {}).values()]
    for task_id in task_ids:
        if task_id:
            state['tasks'][task_id]['status'] = 'stale'
    if key in state['artifacts']:
        state['history'].append({'stage': key, **state['artifacts'].pop(key)})
    stage.update(status='pending', task_id=None)
    for field in ('approval', 'item_states', 'results', 'feedback'):
        stage.pop(field, None)


def reopen_items(state, key, items):
    stage = state['stages'][key]
    require(set(items) <= set(stage['item_states']), 'unknown item in invalidation')
    for item in items:
        cell = stage['item_states'][item]
        if cell.get('task_id'):
            state['tasks'][cell['task_id']]['status'] = 'stale'
        stage['results'].pop(item, None)
        stage['item_states'][item] = dict(status='pending', attempts=cell['attempts'], task_id=None)
    if key in state['artifacts']:
        state['history'].append({'stage': key, **state['artifacts'].pop(key)})
    stage.update(status='in_progress', task_id=None)
    stage.pop('approval', None)


def affected_items(state, task_reader, stage, changed_keys):
    result = []
    for item, cell in state['stages'][stage].get('item_states', {}).items():
        references = state['stages'][stage].get('results', {}).get(item, {}).get('consumed_refs')
        if references is None and cell.get('task_id'):
            references = task_reader(cell['task_id']).get('fanout', {}).get('references')
        # Unknown consumption must never silently preserve stale output.
        if references is None or changed_keys & {ref['reference_key'] for ref in references}:
            result.append(item)
    return result


def invalidate_dependents(state, workflow, origin, changed_keys, task_reader, descendants):
    changed = set(changed_keys)
    affected = {}
    for row in workflow['stages']:
        key = row['id']
        if key == origin or key not in descendants:
            continue
        entry = state['stages'][key]
        if row.get('fanout') and 'item_states' in entry:
            items = affected_items(state, task_reader, key, changed)
            if items:
                affected[key] = items
                reopen_items(state, key, items)
                changed.update(items)
        else:
            # Reviews and nonfanout dependents must review the new assembled version.
            reset_stage(state, key)
    return affected
