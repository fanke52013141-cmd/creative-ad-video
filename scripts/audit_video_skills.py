"""Measure the three deep packages; validate discovery metadata and local links.

Count is CJK characters in original authored Markdown excluding source registers.
This mechanical report is not a creative-quality or research-completeness score.
"""
from pathlib import Path
import json
import re
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEEP = ('script-ad', 'script-shortfilm', 'storyboard-direction')


def main():
    results = []
    errors = []
    for name in DEEP:
        base = ROOT / '.agents/skills' / name
        entry = base / 'SKILL.md'
        if not entry.is_file():
            errors.append('missing ' + name)
            continue
        content = entry.read_text(encoding='utf-8-sig')
        try:
            metadata = yaml.safe_load(content.split('---', 2)[1])
            if metadata['name'] != name or not metadata['description']:
                errors.append(name + ': invalid metadata')
        except (IndexError, KeyError, yaml.YAMLError):
            errors.append(name + ': invalid frontmatter')
        count = 0
        files = []
        for path in sorted(base.rglob('*.md')):
            body = path.read_text(encoding='utf-8-sig')
            for target in re.findall(r'\]\(([^)]+)\)', body):
                if '://' in target or target.startswith('#'):
                    continue
                actual = target.split('#')[0]
                if not (path.parent / actual).exists():
                    errors.append(f'{name}: broken link {path.name}: {target}')
            if any(word in path.stem.lower() for word in ('source', 'evidence', '来源')):
                continue
            # Exclude code/YAML blocks from prose counting.
            prose = re.sub(r'```.*?```', '', body, flags=re.S)
            measured = len(re.findall(r'[\u4e00-\u9fff]', prose))
            files.append({'path': path.relative_to(base).as_posix(), 'cjk': measured})
            count += measured
        if not 10000 <= count <= 20000:
            errors.append(f'{name}: original prose count {count} outside 10000-20000')
        results.append({'skill': name, 'original_cjk': count, 'files': files})
    print(json.dumps({'packages': results, 'errors': errors, 'semantic_evaluation': 'separate'}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == '__main__':
    main()
