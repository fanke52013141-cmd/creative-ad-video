"""Verify a portable production directory from its files, without the source run."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import unicodedata

from .contracts import FlowError, require, text

ASSET_DIRECTORIES = {'character': '人物资产', 'space': '场景资产', 'prop': '物品资产'}
MANIFEST_PATH = '_校验/manifest.json'
REPORT_PATH = '_校验/validation_report.json'


def package_path(root, relative, *, exists=True):
    """Reject portable-path ambiguities as well as escapes and linked ancestors."""
    from .registry import safe_name
    require(text(relative) and '\\' not in relative, f'invalid package path: {relative!r}')
    value = PurePosixPath(relative)
    windows = PureWindowsPath(relative)
    require(not value.is_absolute() and not windows.drive and not windows.root,
            f'absolute package path: {relative}')
    require(all(part not in ('', '.', '..') and ':' not in part for part in relative.split('/')),
            f'unsafe package path: {relative}')
    target = root
    for part in value.parts:
        require(safe_name(part) == part, f'noncanonical package path: {relative}')
        target = target / part
        require(not target.is_symlink() and not getattr(os.path, 'isjunction', lambda _: False)(target),
                f'linked package path: {relative}')
    resolved = target.resolve()
    require(resolved.is_relative_to(root.resolve()) and resolved != root.resolve(),
            f'package path escapes root: {relative}')
    if exists:
        require(target.is_file(), f'missing package file: {relative}')
    return target


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def inspect_image(path):
    """Actual decoding is mandatory; a filename or PNG header is insufficient."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise FlowError('Pillow is required to verify delivery images') from exc
    try:
        with Image.open(path) as source:
            actual_format = source.format
            source.verify()
        with Image.open(path) as source:
            source.load()
            width, height = source.size
        expected = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.webp': 'WEBP'}
        require(expected.get(Path(path).suffix.lower()) == actual_format,
                f'image extension/format mismatch: {Path(path).name}')
        require(width > 0 and height > 0, f'invalid image dimensions: {Path(path).name}')
        return {'width': width, 'height': height, 'format': actual_format.lower()}
    except FlowError:
        raise
    except (OSError, ValueError, SyntaxError) as exc:
        raise FlowError(f'cannot decode delivery image: {Path(path).name}') from exc


def _integer(value, location, *, positive=False):
    require(type(value) is int and value >= (1 if positive else 0), f'invalid integer: {location}')
    return value


def _rows(value, location, *, nonempty=False):
    require(isinstance(value, list) and (value or not nonempty), f'invalid list: {location}')
    require(all(isinstance(row, dict) for row in value), f'invalid row: {location}')
    return value


def _index(rows, field, location):
    require(all(text(row.get(field)) for row in rows), f'missing {field}: {location}')
    result = {row[field]: row for row in rows}
    require(len(result) == len(rows), f'duplicate {field}: {location}')
    return result


def _check_timeline(segment, shots, all_spans):
    video_id = segment['video_id']
    duration = _integer(segment.get('generation_duration_ms'), video_id + '.duration', positive=True)
    spans = _index(_rows(segment.get('source_spans'), video_id + '.source_spans', nonempty=True),
                   'span_id', video_id)
    for span_id, span in spans.items():
        require(span_id not in all_spans, f'duplicate span_id: {span_id}')
        require(span.get('shot_id') in shots, f'unknown source shot: {span_id}')
        start = _integer(span.get('source_start_ms'), span_id + '.start')
        end = _integer(span.get('source_end_ms'), span_id + '.end', positive=True)
        require(start < end <= shots[span['shot_id']]['duration_ms'], f'invalid source range: {span_id}')
        all_spans[span_id] = dict(span, video_id=video_id)
    padding = _index(_rows(segment.get('padding', []), video_id + '.padding'), 'padding_id', video_id)
    require(not set(spans) & set(padding), f'span/padding id collision: {video_id}')
    cursor, referenced = 0, []
    for row in _rows(segment.get('timeline'), video_id + '.timeline', nonempty=True):
        start = _integer(row.get('local_start_ms'), video_id + '.local_start')
        end = _integer(row.get('local_end_ms'), video_id + '.local_end', positive=True)
        require(start == cursor and end > start, f'timeline gap/overlap: {video_id}@{start}')
        require(('span_id' in row) != ('padding_id' in row), f'ambiguous timeline entry: {video_id}')
        if 'span_id' in row:
            span = spans.get(row['span_id'])
            require(span is not None, f'unknown timeline span: {video_id}')
            require(end - start == span['source_end_ms'] - span['source_start_ms'],
                    f'implicit retiming: {row["span_id"]}')
            referenced.append(row['span_id'])
        else:
            pad = padding.get(row['padding_id'])
            require(pad is not None, f'unknown padding: {video_id}')
            require(end - start == pad.get('duration_ms'), f'padding duration mismatch: {video_id}')
            referenced.append(row['padding_id'])
        cursor = end
    require(cursor == duration, f'timeline duration mismatch: {video_id}')
    require(Counter(referenced) == Counter(list(spans) + list(padding)), f'timeline coverage mismatch: {video_id}')


def verify_package(path):
    """Return a fresh successful report or raise FlowError at the first failed check.

    This establishes internal completeness, not authenticity of an unsigned manifest
    or creative quality. The source run's acceptance audit is a separate requirement.
    """
    root = Path(path).absolute()
    require(root.is_dir() and not root.is_symlink()
            and not getattr(os.path, 'isjunction', lambda _: False)(root),
            'package root must be a real directory')
    for directory in (*ASSET_DIRECTORIES.values(), '分镜板', '_校验'):
        target = root / directory
        require(target.is_dir() and not target.is_symlink(), f'missing package directory: {directory}')
    for entry in root.rglob('*'):
        require(not entry.is_symlink() and not getattr(os.path, 'isjunction', lambda _: False)(entry),
                f'linked package entry: {entry.relative_to(root)}')
    try:
        manifest = json.loads(package_path(root, MANIFEST_PATH).read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FlowError('unreadable package manifest') from exc
    require(isinstance(manifest, dict) and manifest.get('schema_version') == '0.2.0', 'unsupported delivery manifest')
    require(manifest.get('platform_binding_status') == 'pending', 'invalid platform binding status')
    require(manifest.get('external_result_status') == 'unverified', 'invalid external result status')
    require(type(manifest.get('synthetic')) is bool, 'missing synthetic declaration')
    require(manifest.get('status') == ('synthetic_package_ready' if manifest['synthetic'] else 'production_package_ready'),
            'package readiness status mismatch')
    profile = manifest.get('platform_profile')
    limits = None
    if profile is not None:
        require(isinstance(profile, dict) and text(profile.get('selected_mode')), 'invalid platform snapshot')
        require(profile.get('status') in ('verified', 'user_supplied', 'test_only', 'unverified'), 'invalid platform verification status')
        require(profile['status'] != 'test_only' or manifest['synthetic'], 'test-only profile cannot claim production readiness')
        limits = profile.get('limits')
        require(isinstance(limits, dict), 'missing platform capacities')
        low = _integer(limits.get('min_duration_ms'), 'platform.min_duration_ms', positive=True)
        high = _integer(limits.get('max_duration_ms'), 'platform.max_duration_ms', positive=True)
        _integer(limits.get('max_images'), 'platform.max_images', positive=True)
        require(low <= high and type(limits.get('supports_multi_shot')) is bool
                and type(limits.get('supports_audio')) is bool, 'invalid platform capacities')
    files = _index(_rows(manifest.get('files'), 'files', nonempty=True), 'path', 'files')
    normalized = [unicodedata.normalize('NFC', name).casefold() for name in files]
    require(len(set(normalized)) == len(normalized), 'portable filename collision')
    require(not {MANIFEST_PATH, REPORT_PATH} & set(files), 'manifest/report must not hash themselves')
    actual = {entry.relative_to(root).as_posix() for entry in root.rglob('*') if entry.is_file()}
    require(actual - {MANIFEST_PATH, REPORT_PATH} == set(files), 'package file inventory mismatch')
    image_count = 0
    texts = {}
    for relative, row in files.items():
        target = package_path(root, relative)
        require(type(row.get('size')) is int and row['size'] > 0 and target.stat().st_size == row['size'],
                f'file size mismatch: {relative}')
        require(text(row.get('sha256')) and row['sha256'] == file_hash(target), f'file hash mismatch: {relative}')
        if row.get('role') in ('asset_image', 'board_image'):
            details = inspect_image(target)
            image_count += 1
            for key in ('width', 'height', 'format'):
                require(row.get(key) == details[key], f'image metadata mismatch: {relative}.{key}')
        elif target.suffix == '.txt':
            try:
                body = target.read_text(encoding='utf-8-sig')
            except UnicodeError as exc:
                raise FlowError(f'invalid UTF-8 text: {relative}') from exc
            require(text(body), f'empty text: {relative}')
            require('{{ref:' not in body, f'unresolved reference token: {relative}')
            texts[relative] = body
        else:
            raise FlowError(f'unexpected payload format: {relative}')
    for relative, role in (('剧本.txt', 'story'), ('详细分镜.txt', 'storyboard'), ('交付清单.txt', 'delivery_list')):
        require(relative in files and files[relative].get('role') == role, f'missing required text: {relative}')

    assets = _rows(manifest.get('assets'), 'assets')
    _index(assets, 'asset_id', 'assets')
    asset_refs = {}
    for asset in assets:
        require(asset.get('kind') in ASSET_DIRECTORIES, f'unknown asset category: {asset.get("asset_id")}')
        requirements = _index(_rows(asset.get('media_requirements'), 'asset.media_requirements'),
                              'reference_key', 'asset.media_requirements')
        declared = _index(_rows(asset.get('references'), 'asset.references'), 'reference_key', 'asset.references')
        require(set(declared) <= set(requirements), f'unregistered asset image: {asset["asset_id"]}')
        require({key for key, row in requirements.items() if row.get('required')} <= set(declared),
                f'missing required asset reference: {asset["asset_id"]}')
        for reference in declared.values():
            key = reference.get('reference_key')
            require(text(key) and key not in asset_refs, f'duplicate/invalid reference key: {key}')
            asset_refs[key] = reference
            relative = reference.get('path')
            require(relative in files and files[relative].get('role') == 'asset_image', f'missing asset reference: {key}')
            if reference.get('coverage_policy') == 'independent':
                require(PurePosixPath(relative).parts[0] == ASSET_DIRECTORIES[asset['kind']], f'wrong asset folder: {key}')
            else:
                require(reference.get('coverage_policy') == 'scene_reference' and relative.startswith('场景资产/'),
                        f'invalid scene coverage: {key}')
            require(PurePosixPath(relative).stem == reference.get('canonical_name'), f'canonical name mismatch: {key}')
            require(reference.get('coverage_policy') == requirements[key].get('coverage_policy'),
                    f'asset coverage policy mismatch: {key}')
    categories = manifest.get('asset_categories')
    require(isinstance(categories, dict), 'missing asset category declaration')
    for kind in ASSET_DIRECTORIES:
        count = sum(asset['kind'] == kind for asset in assets)
        require(categories.get(kind) == {'count': count, 'status': 'applicable' if count else 'not_applicable'},
                f'asset category count/status mismatch: {kind}')

    shots = _index(_rows(manifest.get('shots'), 'shots', nonempty=True), 'shot_id', 'shots')
    for order, shot in enumerate(shots.values(), 1):
        _integer(shot.get('duration_ms'), shot['shot_id'], positive=True)
        require(shot.get('order') == order and text(shot.get('scene_id')), f'invalid shot order/scene: {shot["shot_id"]}')
    segments = _index(_rows(manifest.get('segments'), 'segments', nonempty=True), 'video_id', 'segments')
    boards = _index(_rows(manifest.get('boards'), 'boards', nonempty=True), 'board_id', 'boards')
    all_spans = {}
    references_by_segment = {}
    span_sequence = []
    for order, (video_id, segment) in enumerate(segments.items(), 1):
        require(segment.get('order') == order, f'invalid segment order: {video_id}')
        _check_timeline(segment, shots, all_spans)
        if limits is not None:
            require(segment.get('mode') == profile['selected_mode'], f'segment platform mode mismatch: {video_id}')
            require(limits['min_duration_ms'] <= segment['generation_duration_ms'] <= limits['max_duration_ms'],
                    f'segment exceeds platform duration capacity: {video_id}')
            require(limits['supports_multi_shot'] or len(segment['source_spans']) == 1,
                    f'multi-shot mode unsupported: {video_id}')
        require(len({shots[span['shot_id']]['scene_id'] for span in segment['source_spans']}) == 1,
                f'segment crosses scenes: {video_id}')
        span_sequence.extend((shots[span['shot_id']]['order'], span['source_start_ms']) for span in segment['source_spans'])
        expected_base = f'分镜板/{video_id}/'
        for field, suffix, role in (('prompt_path', '_视频提示词.txt', 'video_prompt'),
                                    ('mapping_path', '_参考图映射.txt', 'reference_mapping')):
            relative = segment.get(field)
            require(relative == expected_base + video_id + suffix and relative in texts
                    and files[relative].get('role') == role, f'missing {field}: {video_id}')
        prompt = texts[segment['prompt_path']]
        mapping = texts[segment['mapping_path']]
        refs = _rows(segment.get('references'), video_id + '.references')
        if limits is not None:
            require(len(refs) <= limits['max_images'], f'reference images exceed platform capacity: {video_id}')
        require([ref.get('planned_slot') for ref in refs] == list(range(1, len(refs) + 1)), f'invalid upload slots: {video_id}')
        ref_index = _index(refs, 'reference_key', video_id + '.references')
        for key, ref in ref_index.items():
            relative = ref.get('path')
            require(relative in files and files[relative].get('role') in ('asset_image', 'board_image'),
                    f'missing segment reference: {video_id}/{key}')
            require(PurePosixPath(relative).stem == ref.get('canonical_name'), f'wrong reference name: {video_id}/{key}')
            require(files[relative]['sha256'] == ref.get('sha256'), f'wrong reference revision: {video_id}/{key}')
            require(text(ref.get('role')), f'missing reference purpose: {video_id}/{key}')
            known = asset_refs.get(key) or boards.get(key)
            require(known is not None and known.get('path') == relative, f'unknown reference binding: {video_id}/{key}')
            require(ref['canonical_name'] in prompt and relative in mapping and ref['canonical_name'] in mapping,
                    f'text/reference mismatch: {video_id}/{key}')
        references_by_segment[video_id] = ref_index
    require(span_sequence == sorted(span_sequence), 'source shot order changed')
    by_shot = defaultdict(list)
    for span in all_spans.values():
        by_shot[span['shot_id']].append((span['source_start_ms'], span['source_end_ms']))
    require(set(by_shot) == set(shots), 'source shots not fully covered')
    for shot_id, ranges in by_shot.items():
        cursor = 0
        for start, end in sorted(ranges):
            require(start == cursor, f'source shot gap/overlap: {shot_id}')
            cursor = end
        require(cursor == shots[shot_id]['duration_ms'], f'source shot duration mismatch: {shot_id}')
    covered = set()
    panel_ids = set()
    max_panels = _integer(manifest.get('board_max_panels'), 'board_max_panels', positive=True)
    require(max_panels <= 4, 'board panel limit exceeds contract')
    for board_id, board in boards.items():
        video_id = board.get('video_id')
        require(video_id in segments, f'unknown board segment: {board_id}')
        relative = board.get('path')
        require(relative in files and files[relative].get('role') == 'board_image', f'missing board image: {board_id}')
        require(relative.startswith(f'分镜板/{video_id}/'), f'wrong board folder: {board_id}')
        require(board.get('kind') in ('panel_sheet', 'single_frame'), f'invalid board kind: {board_id}')
        panels = _rows(board.get('panels'), board_id + '.panels', nonempty=True)
        require(len(panels) <= max_panels and (board['kind'] != 'single_frame' or len(panels) == 1),
                f'invalid panel count: {board_id}')
        require(board.get('reading_order') == [p.get('panel_id') for p in panels], f'board reading order mismatch: {board_id}')
        local_order = {span['span_id']: index for index, span in enumerate(segments[video_id]['source_spans'])}
        panel_order = []
        for panel in panels:
            panel_id = panel.get('panel_id')
            require(text(panel_id) and panel_id not in panel_ids, f'duplicate/invalid panel_id: {board_id}')
            panel_ids.add(panel_id)
            span = all_spans.get(panel.get('span_id'))
            require(span is not None and span['video_id'] == video_id, f'wrong board span: {board_id}')
            moment = _integer(panel.get('source_time_ms'), board_id + '.source_time')
            require(span['source_start_ms'] <= moment < span['source_end_ms'], f'board moment outside span: {board_id}')
            covered.add(panel['span_id'])
            panel_order.append((local_order[panel['span_id']], moment))
        require(panel_order == sorted(panel_order), f'board panel order changed: {board_id}')
        matching = [ref for ref in references_by_segment[video_id].values() if ref['path'] == relative]
        require(matching, f'board not referenced by prompt: {board_id}')
        if board['kind'] != 'single_frame':
            require(not any(ref['role'] in ('first_frame', 'last_frame') for ref in matching),
                    f'multi-panel board used as frame: {board_id}')
    require(covered == set(all_spans), 'board coverage mismatch')
    require({row['path'] for row in files.values() if row.get('role') in ('asset_image', 'board_image')} ==
            {ref['path'] for ref in asset_refs.values()} | {board['path'] for board in boards.values()},
            'unregistered image payload')
    return {'schema_version': '0.2.0', 'passed': True, 'scope': 'portable_package_mechanical',
            'files_checked': len(files), 'images_decoded': image_count, 'segments_checked': len(segments),
            'platform_binding_status': 'pending', 'external_result_status': 'unverified',
            'creative_quality_verified': False, 'synthetic': manifest['synthetic'],
            'platform_capacity_checked': limits is not None}
