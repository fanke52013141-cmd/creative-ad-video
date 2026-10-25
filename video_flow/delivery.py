"""Deterministic TXT/image export of an already accepted production snapshot."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import uuid

from .contracts import FlowError, require, text
from .delivery_validation import (ASSET_DIRECTORIES, MANIFEST_PATH, REPORT_PATH,
                                  file_hash, inspect_image, package_path, verify_package)


def _items(artifacts, name):
    value = artifacts.get(name)
    require(isinstance(value, dict) and isinstance(value.get('items'), list), f'missing artifact: {name}')
    return value['items']


def _name(value, location):
    from .registry import safe_name
    require(text(value), f'missing name: {location}')
    # Never silently sanitize: prompt names and files must agree byte for byte.
    require(safe_name(value) == value, f'noncanonical name: {location}')
    return value


def _seconds(milliseconds):
    require(type(milliseconds) is int and milliseconds >= 0, 'duration must be integer milliseconds')
    return f'{milliseconds / 1000:.3f}'.rstrip('0').rstrip('.')


def _story_text(story):
    lines = []
    for row in story:
        lines += [f"场次：{row['id']}", f"地点：{row['location']}", f"时间：{row['time']}",
                  f"时长：{_seconds(row['duration_ms'])}秒", '出场角色：' + '、'.join(row['characters']),
                  f"场次目标：{row['scene_goal']}", f"动作：{row['action']}"]
        for dialogue in row.get('dialogue', []):
            lines.append(f"{dialogue['speaker_id']}：{dialogue['text']}" +
                         (f"（{dialogue['delivery_note']}）" if dialogue.get('delivery_note') else ''))
        if row.get('narration'):
            lines.append('旁白：' + row['narration'])
        lines.append('')
    return '\n'.join(lines)


def _storyboard_text(shots):
    labels = [('scene_id', '场次'), ('shot_size', '景别'), ('camera_position', '机位'),
              ('primary_camera_motion', '主运镜'), ('action', '动作'), ('start_state', '起始状态'),
              ('end_state', '结束状态'), ('axis', '轴线'), ('cut_motivation', '衔接动机'),
              ('lighting', '光线'), ('sound', '声音')]
    lines = []
    for row in shots:
        lines += [f"镜号：{row['id']}", f"时长：{_seconds(row['duration_ms'])}秒"]
        lines += [f'{label}：{row[field]}' for field, label in labels]
        bindings = row.get('asset_bindings', [])
        lines.append('资产引用：' + '；'.join(f"{ref['asset_id']} / {ref['state_id']} / {ref.get('purpose', '')}" for ref in bindings))
        lines.append('')
    return '\n'.join(lines)


def export_production_package(run, artifacts, output, config):
    """Export accepted artifacts; parent must audit acceptance and hold the run lock.

    No source run files are modified. Only a new sibling temporary directory is
    mutated before independent verification and the final no-overwrite rename.
    """
    bundle = config if 'production' in config else None
    config = config['production'] if bundle else config
    run, output = Path(run).resolve(), Path(output).absolute()
    require(not output.exists() and not output.is_symlink(), 'delivery destination already exists')
    require(output.parent.is_dir(), 'delivery destination parent must exist')
    require(not output.resolve().is_relative_to(run / 'artifacts'), 'delivery cannot overwrite artifact storage')
    encoding = config.get('delivery', {}).get('text_encoding', 'utf-8-sig')
    require(encoding in ('utf-8', 'utf-8-sig'), 'unsupported delivery text encoding')
    story = _items(artifacts, 'story')
    shots = _items(artifacts, 'storyboard')
    assets = _items(artifacts, 'assets')
    media = _items(artifacts, 'asset_media')
    board_media = _items(artifacts, 'board_media')
    prompts = _items(artifacts, 'video_prompts')
    plan = artifacts.get('production_plan', {})
    segments, boards = plan.get('segments'), plan.get('boards')
    require(isinstance(segments, list) and segments and isinstance(boards, list) and boards,
            'missing production plan')
    require(story and shots and prompts, 'production content must not be empty')
    prompt_index = {row.get('video_id'): row for row in prompts}
    require(len(prompt_index) == len(prompts) and set(prompt_index) == {s['video_id'] for s in segments},
            'video prompt segment coverage mismatch')
    media_index = {row.get('reference_key', row.get('item')): row for row in media}
    require(len(media_index) == len(media), 'duplicate asset media reference')
    board_index = {row.get('board_id', row.get('item')): row for row in board_media}
    require(len(board_index) == len(board_media) and set(board_index) == {b['board_id'] for b in boards},
            'board media coverage mismatch')
    temporary = output.with_name(output.name + '.tmp-' + uuid.uuid4().hex)
    temporary.mkdir()
    manifest = {'schema_version': '0.2.0', 'package_id': 'PKG-' + uuid.uuid4().hex,
                'status': 'production_package_ready', 'platform_binding_status': 'pending',
                'external_result_status': 'unverified', 'board_max_panels': config.get('board_max_panels', 4),
                'files': [], 'assets': [], 'asset_categories': {}, 'segments': [], 'boards': [],
                'shots': [{'shot_id': row['id'], 'duration_ms': row['duration_ms'],
                           'order': row['order'], 'scene_id': row['scene_id']} for row in shots],
                'source_content_hashes': {name: hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
                    for name, value in artifacts.items() if isinstance(value, dict)}}
    manifest['synthetic'] = config.get('media_mode') == 'mock'
    if bundle:
        platform, provider = bundle['platform'], bundle['provider']
        selected_mode = config['selected_mode']
        require(selected_mode in platform['modes'], 'unknown selected platform mode')
        manifest['platform_profile'] = {'profile_id': platform['profile_id'], 'status': platform['status'],
            'selected_mode': selected_mode, 'limits': platform['modes'][selected_mode]}
        manifest['synthetic'] = manifest['synthetic'] or platform['status'] == 'test_only' or provider.get('test_only', False)
    if manifest['synthetic']:
        manifest['status'] = 'synthetic_package_ready'
    files = {}
    by_source = {}
    source_rows = {}
    reference_paths = {}

    def add_text(relative, body, role):
        require(text(body), f'empty generated text: {relative}')
        target = package_path(temporary, relative, exists=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body.rstrip() + '\n', encoding=encoding)
        record = {'path': relative, 'role': role, 'size': target.stat().st_size, 'sha256': file_hash(target)}
        require(relative not in files, f'duplicate delivery file: {relative}')
        files[relative] = record

    def add_image(row, relative):
        source = package_path(run, row['file'])
        require(file_hash(source) == row.get('sha256'), f'media hash mismatch: {row["file"]}')
        details = inspect_image(source)
        require(all(row.get(key, actual) == actual for key, actual in details.items()),
                f'media metadata mismatch: {row["file"]}')
        require(relative not in files, f'duplicate delivery image: {relative}')
        target = package_path(temporary, relative, exists=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        require(file_hash(target) == row['sha256'], f'copy hash mismatch: {relative}')
        role = 'asset_image' if PurePosixPath(relative).parts[0] in ASSET_DIRECTORIES.values() else 'board_image'
        files[relative] = {'path': relative, 'role': role, 'size': target.stat().st_size,
                           'sha256': row['sha256'], **details}
        by_source[(row['file'], row['sha256'])] = relative
        source_rows[(row['file'], row['sha256'])] = row

    try:
        for directory in (*ASSET_DIRECTORIES.values(), '分镜板', '_校验'):
            (temporary / directory).mkdir()
        add_text('剧本.txt', _story_text(story), 'story')
        add_text('详细分镜.txt', _storyboard_text(shots), 'storyboard')
        # First copy independently required media. Scene-covered requirements are
        # resolved in a second pass so registry order cannot change the outcome.
        for asset in assets:
            asset_id = asset['id']
            kind = asset['kind']
            require(kind in ASSET_DIRECTORIES, f'unknown asset kind: {asset_id}')
            asset_record = {'asset_id': asset_id, 'kind': kind,
                            'media_requirements': asset['media_requirements'], 'references': []}
            manifest['assets'].append(asset_record)
            for requirement in asset['media_requirements']:
                key = requirement['reference_key']
                row = media_index.get(key)
                if not requirement['required'] and row is None:
                    continue
                if requirement['coverage_policy'] == 'scene_reference' and row is None:
                    continue
                require(row is not None, f'missing required asset image: {key}')
                require(row.get('asset_id') == asset_id and row.get('state_id') == requirement['state_id']
                        and row.get('view') == requirement['view'], f'asset media binding mismatch: {key}')
                stem = _name(row.get('canonical_name'), key)
                suffix = Path(row['file']).suffix.lower()
                relative = ASSET_DIRECTORIES[kind] + '/' + stem + suffix
                add_image(row, relative)
                reference_paths[key] = relative
                asset_record['references'].append({'reference_key': key, 'canonical_name': stem,
                    'path': relative, 'media_revision': row['revision'],
                    'coverage_policy': requirement['coverage_policy'], 'required': requirement['required']})
        used_media = set(reference_paths)
        require(set(media_index) == used_media, 'asset media contains unregistered or duplicate image requirements')
        for asset, asset_record in zip(assets, manifest['assets']):
            for requirement in asset['media_requirements']:
                key = requirement['reference_key']
                if key in reference_paths or not requirement['required']:
                    continue
                covered_by = requirement.get('covered_by_reference_key')
                require(requirement['coverage_policy'] == 'scene_reference' and covered_by in reference_paths,
                        f'missing required asset coverage: {key}')
                relative = reference_paths[covered_by]
                require(relative.startswith('场景资产/'), f'asset must be covered by scene image: {key}')
                reference_paths[key] = relative
                asset_record['references'].append({'reference_key': key, 'canonical_name': PurePosixPath(relative).stem,
                    'path': relative, 'coverage_policy': 'scene_reference', 'covered_by': covered_by, 'required': True})
        for kind in ASSET_DIRECTORIES:
            count = sum(asset['kind'] == kind for asset in assets)
            manifest['asset_categories'][kind] = {'count': count, 'status': 'applicable' if count else 'not_applicable'}
        for board in boards:
            board_id, video_id = board['board_id'], board['video_id']
            _name(board_id, 'board_id')
            _name(video_id, 'video_id')
            row = board_index[board_id]
            stem = _name(row.get('canonical_name'), board_id)
            relative = f"分镜板/{video_id}/{stem}{Path(row['file']).suffix.lower()}"
            add_image(row, relative)
            require(board_id not in reference_paths, f'board/reference id collision: {board_id}')
            reference_paths[board_id] = relative
            manifest['boards'].append({**board, 'path': relative})
        for segment in segments:
            video_id = segment['video_id']
            prompt = prompt_index[video_id]
            require(prompt.get('duration_ms') == segment['generation_duration_ms']
                    and prompt.get('mode') == segment['mode'],
                    f'prompt/plan mismatch: {video_id}')
            require(isinstance(prompt.get('timeline'), list) and len(prompt['timeline']) == len(segment['timeline']),
                    f'prompt/plan timeline coverage mismatch: {video_id}')
            for actual, planned in zip(prompt['timeline'], segment['timeline']):
                require(all(actual.get(key) == planned.get(key) for key in ('local_start_ms', 'local_end_ms', 'span_id', 'padding_id')),
                        f'prompt/plan timeline mismatch: {video_id}')
            refs = []
            for reference in prompt['references']:
                key = reference['reference_key']
                relative = by_source.get((reference['file'], reference['sha256']))
                require(relative is not None and reference_paths.get(key) == relative, f'unresolved reference: {video_id}/{key}')
                require(PurePosixPath(relative).stem == reference['canonical_name'], f'reference name mismatch: {video_id}/{key}')
                source_row = source_rows[(reference['file'], reference['sha256'])]
                require(reference.get('media_revision', source_row['revision']) == source_row['revision'],
                        f'reference revision mismatch: {video_id}/{key}')
                refs.append({k: reference[k] for k in ('reference_key', 'canonical_name', 'sha256', 'planned_slot', 'role')})
                refs[-1]['path'] = relative
            prompt_path = f'分镜板/{video_id}/{video_id}_视频提示词.txt'
            mapping_path = f'分镜板/{video_id}/{video_id}_参考图映射.txt'
            add_text(prompt_path, prompt['prompt'], 'video_prompt')
            mapping = [f'生成片段：{video_id}', f"模式：{segment['mode']}",
                       f"目标时长：{_seconds(segment['generation_duration_ms'])}秒",
                       '绑定状态：计划上传顺序；实际上传后核对平台显示标签。', '']
            for reference in refs:
                mapping += [f"计划上传位{reference['planned_slot']}：{reference['path']}",
                            f"正式名称：{reference['canonical_name']}", f"用途：{reference['role']}", '']
            mapping += ['源镜头及保留范围：']
            for span in segment['source_spans']:
                mapping.append(f"{span['shot_id']}：{_seconds(span['source_start_ms'])}—{_seconds(span['source_end_ms'])}秒")
            if segment.get('padding'):
                mapping += ['存在生成补时，补时不计入源剧本时长；按时间映射保留所需区间。']
            add_text(mapping_path, '\n'.join(mapping), 'reference_mapping')
            manifest['segments'].append({**segment, 'prompt_path': prompt_path,
                                         'mapping_path': mapping_path, 'references': refs})
        listing = [f"制作包：{manifest['package_id']}",
                   ('状态：合成测试制作包；不能作为实际视觉效果验收。' if manifest['synthetic'] else
                    '状态：前期制作包就绪；外部视频效果尚未验证。'),
                   '平台素材绑定：待执行，请按每段参考图映射上传并核对。',
                   f'剧本场数：{len(story)}；镜头数：{len(shots)}；生成片段数：{len(segments)}；分镜板数：{len(boards)}。']
        for kind, directory in ASSET_DIRECTORIES.items():
            category = manifest['asset_categories'][kind]
            listing.append(f"{directory}：{category['count']}项" + ('；不适用。' if not category['count'] else '。'))
        listing += ['', '文件清单：', *sorted(files), '交付清单.txt', '_校验/manifest.json', '_校验/validation_report.json']
        add_text('交付清单.txt', '\n'.join(listing), 'delivery_list')
        manifest['files'] = [files[key] for key in sorted(files)]
        (temporary / MANIFEST_PATH).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        report = verify_package(temporary)
        (temporary / REPORT_PATH).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        # rename does not replace an existing directory on Windows; the explicit
        # second check also gives a useful message if a competing export won.
        require(not output.exists(), 'delivery destination created during export')
        temporary.rename(output)
        return {'package': str(output), 'manifest': manifest, 'validation': report}
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
