"""Pure, deterministic production segmentation and coverage validation.

This module plans reference boards; it neither generates pictures nor claims that
an arbitrary model will follow the planned timing or camera instructions.
"""
from __future__ import annotations

from .contracts import FlowError, require, text


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _shots(storyboard):
    require(isinstance(storyboard, dict), 'storyboard must be an object')
    rows = storyboard.get('items')
    require(isinstance(rows, list) and rows, 'storyboard items must not be empty')
    result, ids, orders = [], set(), []
    for row in rows:
        require(isinstance(row, dict), 'shot must be an object')
        shot_id = row.get('shot_id', row.get('id'))
        require(text(shot_id) and shot_id not in ids, 'shot ids must be unique and nonempty')
        require(not ('shot_id' in row and 'id' in row) or row['shot_id'] == row['id'],
                f'{shot_id}: conflicting shot ids')
        require(text(row.get('scene_id')), f'{shot_id}: scene_id required')
        require(_integer(row.get('duration_ms'), 1), f'{shot_id}: positive integer duration_ms required')
        require(_integer(row.get('order'), 1), f'{shot_id}: positive integer order required')
        ids.add(shot_id)
        orders.append(row['order'])
        result.append(dict(row, shot_id=shot_id))
    require(orders == sorted(set(orders)), 'storyboard order must be unique and ascending')
    return result


def _limits(platform):
    require(isinstance(platform, dict), 'platform must be an object')
    low, high = platform.get('min_duration_ms'), platform.get('max_duration_ms')
    require(_integer(low, 1) and _integer(high, 1) and low <= high,
            'platform requires explicit positive min/max_duration_ms')
    require(type(platform.get('supports_multi_shot')) is bool,
            'platform requires explicit supports_multi_shot')
    return low, high, platform['supports_multi_shot']


def _split_shot(shot, high):
    duration = shot['duration_ms']
    if duration <= high:
        return [(0, duration)]
    boundaries = shot.get('split_points_ms')
    require(isinstance(boundaries, list) and boundaries,
            f"needs_input: {shot['shot_id']} exceeds capacity; explicit split_points_ms required")
    require(all(_integer(x, 1) and x < duration for x in boundaries) and
            boundaries == sorted(set(boundaries)), f"{shot['shot_id']}: invalid split_points_ms")
    points, result, start = boundaries + [duration], [], 0
    while start < duration:
        available = [point for point in points if start < point <= start + high]
        require(available, f"needs_input: {shot['shot_id']} has no usable split boundary after {start}")
        end = max(available)
        result.append((start, end))
        start = end
    return result


def _references(shot):
    refs = shot.get('reference_keys', [])
    require(isinstance(refs, list) and all(text(x) for x in refs),
            f"{shot['shot_id']}: reference_keys must be strings")
    return refs


def _boundary_state(shot, time):
    if time == 0:
        return shot.get('start_state', '')
    if time == shot['duration_ms']:
        return shot.get('end_state', '')
    # A split offset does not reveal the actor's intermediate pose. Carry the
    # explicitly authored state when available; never relabel the whole shot's
    # start/end state as an observed intermediate state.
    return shot.get('split_states', {}).get(str(time), '')


def build_production_plan(storyboard, platform, *, target_duration_ms=None,
                          max_panels=4, allow_padding=True):
    """Group adjacent source spans without crossing scenes or inventing action.

    target_duration_ms is a preference, not a new platform capacity. It closes a
    group once reached, but a short group may grow to reach the platform minimum.
    """
    shots = _shots(storyboard)
    low, high, multi = _limits(platform)
    require(_integer(max_panels, 1) and max_panels <= 4, 'max_panels must be 1..4')
    require(type(allow_padding) is bool, 'allow_padding must be boolean')
    target = high if target_duration_ms is None else target_duration_ms
    require(_integer(target, 1) and low <= target <= high, 'target_duration_ms outside platform limits')
    mode = platform.get('mode', 'reference')
    require(text(mode), 'platform mode must be nonempty')
    pieces = []
    for shot in shots:
        for start, end in _split_shot(shot, high):
            pieces.append({'shot': shot, 'start': start, 'end': end})
    groups, current, total = [], [], 0
    for piece in pieces:
        duration = piece['end'] - piece['start']
        if current and (current[-1]['shot']['scene_id'] != piece['shot']['scene_id'] or
                        not multi or total + duration > high or total >= target):
            groups.append(current)
            current, total = [], 0
        current.append(piece)
        total += duration
    if current:
        groups.append(current)
    segments, boards, span_counter = [], [], 0
    for order, group in enumerate(groups, 1):
        video_id = f'V{order:03d}'
        segment = {'video_id': video_id, 'order': order, 'mode': mode,
                   'scene_id': group[0]['shot']['scene_id'], 'source_spans': [],
                   'generation_duration_ms': 0, 'timeline': [], 'padding': [],
                   'continuity_in': {'shot_id': group[0]['shot']['shot_id'],
                                     'source_time_ms': group[0]['start'],
                                     'state': _boundary_state(group[0]['shot'], group[0]['start'])},
                   'continuity_out': {'shot_id': group[-1]['shot']['shot_id'],
                                      'source_time_ms': group[-1]['end'],
                                      'state': _boundary_state(group[-1]['shot'], group[-1]['end'])},
                   'reference_keys': []}
        panels = []
        for piece in group:
            span_counter += 1
            span_id = f'SPAN{span_counter:04d}'
            shot, start, end = piece['shot'], piece['start'], piece['end']
            span = {'span_id': span_id, 'shot_id': shot['shot_id'],
                    'source_start_ms': start, 'source_end_ms': end}
            segment['source_spans'].append(span)
            local_start = segment['generation_duration_ms']
            segment['generation_duration_ms'] += end - start
            segment['timeline'].append({'span_id': span_id, 'local_start_ms': local_start,
                                        'local_end_ms': segment['generation_duration_ms']})
            refs = _references(shot)
            segment['reference_keys'] = list(dict.fromkeys(segment['reference_keys'] + refs))
            panels.append({'panel_id': f'PANEL{span_counter:04d}', 'span_id': span_id,
                           'source_time_ms': start, 'frame_role': 'keyframe',
                           'composition': shot.get('action', ''), 'reference_keys': refs})
        if segment['generation_duration_ms'] < low:
            require(allow_padding, f'needs_input: {video_id} shorter than platform minimum; padding disabled')
            gap = low - segment['generation_duration_ms']
            padding_id = f'{video_id}-HOLD'
            segment['padding'].append({'padding_id': padding_id, 'duration_ms': gap,
                                       'purpose': 'hold_end_frame', 'discard_in_edit': True})
            segment['timeline'].append({'padding_id': padding_id,
                                        'local_start_ms': segment['generation_duration_ms'], 'local_end_ms': low})
            segment['generation_duration_ms'] = low
        segments.append(segment)
        for offset in range(0, len(panels), max_panels):
            block = panels[offset:offset+max_panels]
            boards.append({'board_id': f'SB{len(boards)+1:03d}', 'video_id': video_id,
                           'kind': 'panel_sheet', 'layout': 'ordered',
                           'reading_order': [p['panel_id'] for p in block], 'panels': block,
                           'reference_keys': list(dict.fromkeys(ref for p in block for ref in p['reference_keys']))})
    result = {'schema_version': '0.2.0', 'type': 'production_plan', 'segments': segments, 'boards': boards}
    validate_production_plan(result, storyboard, platform, max_panels=max_panels)
    return result


def validate_production_plan(plan, storyboard, platform, *, max_panels=4):
    """Reject missing/overlapping source coverage, time gaps and unusable boards."""
    shots = _shots(storyboard)
    low, high, multi = _limits(platform)
    require(_integer(max_panels, 1) and max_panels <= 4, 'max_panels must be 1..4')
    require(isinstance(plan, dict) and plan.get('type') == 'production_plan' and
            plan.get('schema_version') == '0.2.0', 'expected v0.2 production_plan')
    segments, boards = plan.get('segments'), plan.get('boards')
    require(isinstance(segments, list) and segments, 'production plan needs segments')
    require(isinstance(boards, list) and boards, 'production plan needs boards')
    shot_map = {s['shot_id']: s for s in shots}
    spans, video_ids, coverage, sequence = {}, set(), {s['shot_id']: [] for s in shots}, []
    for index, segment in enumerate(segments, 1):
        require(isinstance(segment, dict), 'segment must be an object')
        video_id = segment.get('video_id')
        require(text(video_id) and video_id not in video_ids, 'video_id must be unique')
        video_ids.add(video_id)
        require(segment.get('order') == index, f'{video_id}: segment order must be contiguous')
        require(text(segment.get('mode')), f'{video_id}: mode required')
        require(segment['mode'] == platform.get('mode', 'reference'), f'{video_id}: mode differs from profile')
        duration = segment.get('generation_duration_ms')
        require(_integer(duration, 1) and low <= duration <= high, f'{video_id}: duration outside platform limits')
        source = segment.get('source_spans')
        require(isinstance(source, list) and source, f'{video_id}: source_spans required')
        require(multi or len(source) == 1, f'{video_id}: profile does not permit multiple source spans')
        local_spans, scene_ids = {}, set()
        for span in source:
            require(isinstance(span, dict), f'{video_id}: invalid source span')
            sid, shot_id = span.get('span_id'), span.get('shot_id')
            require(text(sid) and sid not in spans, 'span_id must be globally unique')
            require(shot_id in shot_map, f'{sid}: unknown shot_id')
            start, end = span.get('source_start_ms'), span.get('source_end_ms')
            require(_integer(start) and _integer(end, 1) and start < end <= shot_map[shot_id]['duration_ms'],
                    f'{sid}: source interval invalid')
            if start > 0 or end < shot_map[shot_id]['duration_ms']:
                allowed = shot_map[shot_id].get('split_points_ms', [])
                require((start == 0 or start in allowed) and
                        (end == shot_map[shot_id]['duration_ms'] or end in allowed),
                        f'{sid}: source split is not an explicit action boundary')
            scene_ids.add(shot_map[shot_id]['scene_id'])
            coverage[shot_id].append((start, end))
            sequence.append((shot_map[shot_id]['order'], start))
            spans[sid] = dict(span, video_id=video_id)
            local_spans[sid] = end-start
        require(len(scene_ids) == 1, f'{video_id}: segment cannot cross scenes')
        if 'scene_id' in segment:
            require(segment['scene_id'] in scene_ids, f'{video_id}: wrong scene_id')
        for field, span, time_field in (('continuity_in', source[0], 'source_start_ms'),
                                        ('continuity_out', source[-1], 'source_end_ms')):
            continuity = segment.get(field)
            require(isinstance(continuity, dict) and continuity.get('shot_id') == span['shot_id'] and
                    continuity.get('source_time_ms') == span[time_field],
                    f'{video_id}: invalid {field} source binding')
        refs = segment.get('reference_keys')
        expected_refs = {ref for span in source for ref in _references(shot_map[span['shot_id']])}
        require(isinstance(refs, list) and all(text(ref) for ref in refs) and
                len(refs) == len(set(refs)) and set(refs) == expected_refs,
                f'{video_id}: reference_keys do not cover source requirements')
        padding = segment.get('padding')
        require(isinstance(padding, list), f'{video_id}: padding must be an array')
        pads = {}
        for pad in padding:
            require(isinstance(pad, dict) and text(pad.get('padding_id')) and
                    pad['padding_id'] not in pads and _integer(pad.get('duration_ms'), 1) and
                    pad.get('purpose') == 'hold_end_frame' and pad.get('discard_in_edit') is True,
                    f'{video_id}: padding must be declared end hold')
            pads[pad['padding_id']] = pad['duration_ms']
        if pads:
            require(sum(local_spans.values()) < low and len(pads) == 1 and
                    sum(pads.values()) == low-sum(local_spans.values()),
                    f'{video_id}: padding must only satisfy the platform minimum')
        timeline = segment.get('timeline')
        require(isinstance(timeline, list) and timeline, f'{video_id}: timeline required')
        cursor, seen_spans, seen_padding = 0, [], []
        for entry in timeline:
            require(isinstance(entry, dict), f'{video_id}: invalid timeline entry')
            start, end = entry.get('local_start_ms'), entry.get('local_end_ms')
            require(_integer(start) and _integer(end, 1) and start == cursor and end > start,
                    f'{video_id}: timeline gap/overlap at {cursor}')
            require(('span_id' in entry) != ('padding_id' in entry), f'{video_id}: timeline must bind one source or padding')
            if 'span_id' in entry:
                ref = entry['span_id']
                require(ref in local_spans and not seen_padding and end-start == local_spans[ref],
                        f'{video_id}: invalid source timeline duration or order')
                seen_spans.append(ref)
            else:
                ref = entry['padding_id']
                require(ref in pads and end-start == pads[ref], f'{video_id}: invalid padding timeline')
                seen_padding.append(ref)
            cursor = end
        require(cursor == duration, f'{video_id}: timeline does not match duration')
        require(seen_spans == list(local_spans) and len(seen_padding) == len(set(seen_padding)) and
                set(seen_padding) == set(pads), f'{video_id}: timeline coverage/order mismatch')
    require(sequence == sorted(sequence), 'source spans reorder storyboard shots')
    for shot_id, intervals in coverage.items():
        cursor = 0
        for start, end in intervals:
            require(start == cursor, f'{shot_id}: source coverage gap/overlap at {cursor}')
            cursor = end
        require(cursor == shot_map[shot_id]['duration_ms'], f'{shot_id}: incomplete source coverage')
    board_ids, panel_ids, represented, board_sequence = set(), set(), set(), []
    asset_reference_keys = {ref for shot in shots for ref in _references(shot)}
    video_order = {segment['video_id']: segment['order'] for segment in segments}
    for board in boards:
        require(isinstance(board, dict), 'board must be an object')
        board_id, video_id = board.get('board_id'), board.get('video_id')
        require(text(board_id) and board_id not in board_ids, 'board_id must be unique')
        require(board_id not in asset_reference_keys, f'{board_id}: board id collides with asset reference key')
        board_ids.add(board_id)
        require(video_id in video_ids, f'{board_id}: unknown video_id')
        kind, panels = board.get('kind'), board.get('panels')
        require(kind in {'panel_sheet', 'single_frame'}, f'{board_id}: invalid board kind')
        require(isinstance(panels, list) and 1 <= len(panels) <= max_panels and
                (kind != 'single_frame' or len(panels) == 1), f'{board_id}: invalid panel count')
        require(board.get('reading_order') == [p.get('panel_id') for p in panels if isinstance(p, dict)],
                f'{board_id}: reading order differs from panels')
        board_positions, expected_board_refs = [], set()
        for panel in panels:
            require(isinstance(panel, dict), f'{board_id}: invalid panel')
            pid, sid = panel.get('panel_id'), panel.get('span_id')
            require(text(pid) and pid not in panel_ids, 'panel_id must be globally unique')
            panel_ids.add(pid)
            require(sid in spans and spans[sid]['video_id'] == video_id, f'{pid}: panel has wrong source span')
            span = spans[sid]
            time = panel.get('source_time_ms')
            require(_integer(time) and span['source_start_ms'] <= time <= span['source_end_ms'],
                    f'{pid}: source_time_ms outside span')
            role = panel.get('frame_role')
            require(role in {'keyframe','first_frame','last_frame'}, f'{pid}: invalid frame_role')
            require(kind == 'single_frame' or role == 'keyframe', f'{pid}: multi-panel board cannot be first/last frame')
            represented.add(sid)
            board_positions.append((shot_map[span['shot_id']]['order'], time))
            expected_board_refs.update(_references(shot_map[span['shot_id']]))
        board_refs = board.get('reference_keys')
        require(isinstance(board_refs, list) and all(text(ref) for ref in board_refs) and
                len(board_refs) == len(set(board_refs)) and set(board_refs) == expected_board_refs,
                f'{board_id}: reference_keys do not cover board source requirements')
        require(board_positions == sorted(board_positions), f'{board_id}: panels reorder source')
        board_sequence.extend((video_order[video_id], *position) for position in board_positions)
    require(board_sequence == sorted(board_sequence), 'board list reorders source frames')
    require(represented == set(spans), 'boards must cover every source span')
    return plan
