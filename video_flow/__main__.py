"""CLI for the local Video Flow execution protocol."""
import argparse
import json
import sys
from pathlib import Path
from . import engine
from .contracts import FlowError
from .storage import read, tree_digest


def main():
    parser = argparse.ArgumentParser(prog='python -m video_flow')
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('run')
    init.add_argument('--brief', required=True)
    init.add_argument('--approval', choices=['key_decisions', 'automatic'], default='key_decisions')
    init.add_argument('--media', action='store_true', help='include reference-media fanout stages')
    init.add_argument('--production-config', default=None, help='opt in to v0.2 external production workflow')
    for name in ('status', 'audit', 'preflight'):
        sub.add_parser(name).add_argument('run')
    package = sub.add_parser('package')
    package.add_argument('run')
    package.add_argument('--format', choices=['audit', 'external-production'], default=None)
    package.add_argument('--out', default=None)
    check = sub.add_parser('validate')
    check.add_argument('run')
    check.add_argument('--scope', choices=['delivery'], default='delivery')
    sub.add_parser('verify-package').add_argument('path')
    imported = sub.add_parser('import-media')
    imported.add_argument('run')
    imported.add_argument('--reference-key', required=True)
    imported.add_argument('--file', required=True)
    imported.add_argument('--stage', choices=['asset_media', 'board_media'], default='asset_media')
    raw = sub.add_parser('import-input')
    raw.add_argument('run')
    raw.add_argument('--kind', choices=['story'], required=True)
    raw.add_argument('--file', required=True)
    sub.add_parser('protocol')
    dispatch = sub.add_parser('dispatch')
    dispatch.add_argument('run')
    dispatch.add_argument('stage')
    dispatch.add_argument('item', nargs='?', help='fanout item id (media stages)')
    bind = sub.add_parser('bind')
    bind.add_argument('run')
    bind.add_argument('task_id')
    bind.add_argument('agent_id')
    submit = sub.add_parser('submit')
    submit.add_argument('run')
    submit.add_argument('task_id')
    retry = sub.add_parser('retry')
    retry.add_argument('run')
    retry.add_argument('task_id')
    retry.add_argument('--reason', required=True)
    approval = sub.add_parser('approve')
    approval.add_argument('run')
    approval.add_argument('stage')
    approval.add_argument('--actor', required=True)
    approval.add_argument('--reason', required=True)
    invalid = sub.add_parser('invalidate')
    invalid.add_argument('run')
    invalid.add_argument('stage')
    invalid.add_argument('--reason', required=True)
    invalid.add_argument('--item', default=None, help='reopen a single fanout item instead of the whole stage')
    sub.add_parser('doctor')
    args = vars(parser.parse_args())
    command = args.pop('command')
    try:
        if command == 'doctor':
            workflow = engine.load_yaml(engine.ROOT / 'config/workflow.yaml')
            from .production_runtime import materialize_workflow
            legacy = materialize_workflow(workflow)
            production = materialize_workflow(workflow, True)
            engine.graph_check(legacy)
            engine.graph_check(production)
            names = {x['skill'] for x in production['stages']} - {'$writer'} | {'script-ad', 'script-shortfilm'}
            for row in legacy['stages'] + production['stages']:
                names.update(row.get('fanout', {}).get('skill_by_kind', {}).values())
            missing = [x for x in sorted(names) if not (engine.ROOT / '.agents/skills' / x / 'SKILL.md').is_file()]
            if missing:
                raise FlowError('missing skills: ' + ', '.join(missing))
            result = {'status': 'ok', 'stages': len(legacy['stages']), 'production_stages': len(production['stages']), 'skills': {x: tree_digest(engine.ROOT / '.agents/skills' / x) for x in sorted(names)},
                      'subagent_execution': 'requires Codex coordinator tools; not spawned by this CLI', 'enforcement': 'acceptance'}
        elif command == 'init':
            result = engine.initialize(args['run'], read(Path(args['brief'])), args['approval'], media=args['media'], production_config=args['production_config'])
        else:
            result = getattr(engine, command.replace('-', '_'))(**args)
        if result.get('status') in ('blocked', 'violations') or result.get('passed') is False:
            print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
            raise SystemExit(1)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (FlowError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'blocked', 'reason': str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
