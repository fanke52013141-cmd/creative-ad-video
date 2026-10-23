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
    for name in ('status', 'package'):
        sub.add_parser(name).add_argument('run')
    dispatch = sub.add_parser('dispatch')
    dispatch.add_argument('run')
    dispatch.add_argument('stage')
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
    sub.add_parser('doctor')
    args = vars(parser.parse_args())
    command = args.pop('command')
    try:
        if command == 'doctor':
            workflow = engine.load_yaml(engine.ROOT / 'config/workflow.yaml')
            engine.graph_check(workflow)
            names = {x['skill'] for x in workflow['stages']} - {'$writer'} | {'script-ad', 'script-shortfilm'}
            missing = [x for x in sorted(names) if not (engine.ROOT / '.agents/skills' / x / 'SKILL.md').is_file()]
            if missing:
                raise FlowError('missing skills: ' + ', '.join(missing))
            result = {'status': 'ok', 'stages': len(workflow['stages']), 'skills': {x: tree_digest(engine.ROOT / '.agents/skills' / x) for x in sorted(names)},
                      'subagent_execution': 'requires Codex coordinator tools; not spawned by this CLI', 'enforcement': 'acceptance'}
        elif command == 'init':
            result = engine.initialize(args['run'], read(Path(args['brief'])), args['approval'])
        else:
            result = getattr(engine, command)(**args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (FlowError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'blocked', 'reason': str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
