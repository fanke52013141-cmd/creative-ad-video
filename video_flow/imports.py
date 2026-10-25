"""Explicit local import operations; never fabricate a spawned worker identity."""
from pathlib import Path
import shutil
import uuid
from .contracts import require, FlowError
from .storage import read, write, digest, inside, transaction


def import_media(run, reference_key, file, stage='asset_media'):
    from . import engine
    run, source = Path(run), Path(file).resolve()
    require(stage in ('asset_media', 'board_media'), 'unsupported import media stage')
    require(source.is_file(), 'import source file missing')
    state = read(run / 'checkpoint.json')
    engine.integrity(run, state)
    require(state.get('version') == '0.2.0', 'media import requires v0.2 run')
    packet = engine.dispatch(run, stage, reference_key, executor_type='import')
    task_id = packet['task_id']
    actor = 'import:' + task_id
    engine.bind(run, task_id, actor)
    destination = inside(run, packet['fanout']['target_file'])
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open('rb') as src, destination.open('xb') as dst:
            shutil.copyfileobj(src, dst)
        candidate = {'schema_version': '0.2.0', 'task_id': task_id, 'type': 'media_item', 'item': reference_key,
                     'file': packet['fanout']['target_file'], 'sha256': digest(destination),
                     'prompt': 'User supplied local image import; visual fidelity requires independent review.',
                     'source': 'imported', 'original_filename': source.name}
        base = Path(packet['output_root'])
        write(base / 'candidate.json', candidate)
        write(base / 'receipt.json', {'task_id': task_id, 'agent_id': actor, 'skill_sha256': packet['skill_sha256'],
                                     'input_hashes': packet['input_hashes'], 'output_sha256': digest(base / 'candidate.json')})
        result = engine.submit(run, task_id)
        result['import_operation'] = {'task_id': task_id, 'actor': actor, 'source_sha256': candidate['sha256']}
        return result
    except (OSError, ValueError) as exc:
        engine.retry(run, task_id, 'Import failed: ' + str(exc))
        raise


def import_input(run, kind, file):
    """Register raw story for an actual writer to convert without changing its facts."""
    from . import engine
    require(kind == 'story', 'only raw story input is supported')
    run, source = Path(run), Path(file).resolve()
    require(source.is_file(), 'story import file missing')
    body = source.read_text(encoding='utf-8-sig')
    require(body.strip(), 'story import must be nonempty UTF-8 text')
    with transaction(run) as state:
        engine.integrity(run, state)
        require(state.get('version') == '0.2.0', 'story import requires v0.2 run')
        require(state['stages']['story']['status'] == 'pending' and not state['stages']['story']['attempts'], 'import story before first story dispatch; use a new run for changed facts')
        require('story_source' not in state, 'story source already registered; create a new run to replace it')
        rel = 'inputs/imported/' + uuid.uuid4().hex + '.txt'
        path = inside(run, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding='utf-8')
        state['story_source'] = {'path': rel, 'sha256': digest(path), 'source_name': source.name}
        engine.event(state, 'import_input', kind=kind, sha256=digest(path))
    return {'status': 'registered', 'kind': kind, 'next_stage': 'story', 'independent_review_required': True}
