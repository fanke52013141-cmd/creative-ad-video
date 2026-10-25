"""Reference-bound prompt validation and deterministic text rendering."""
from __future__ import annotations
import re
from .contracts import require, text

TOKEN = re.compile(r'\{\{ref:([^{}]+)\}\}')


def reference_text(value, references, tag_template='@图片{slot}'):
    by_key = {row['reference_key']: row for row in references}
    used = set(TOKEN.findall(value))
    require(used <= set(by_key), 'prompt contains unknown reference token: ' + ', '.join(sorted(used - set(by_key))))
    def replace(match):
        row = by_key[match[1]]
        return tag_template.format(slot=row['planned_slot']) + f"（{row['canonical_name']}）"
    rendered = TOKEN.sub(replace, value)
    require('{{' not in rendered and '}}' not in rendered, 'unresolved prompt token')
    # Platform tags belong exclusively to the renderer, never free-form worker text.
    require(not re.search(r'@(?:图片|图|image)\s*\d', value, re.I), 'author must use reference tokens instead of platform slots')
    prefix, suffix = tag_template.split('{slot}')
    require(not re.search(re.escape(prefix) + r'\d+' + re.escape(suffix), value), 'author must use reference tokens instead of raw platform tags')
    return rendered


def validate_and_render(candidate, spec, mode=None):
    segment, references = spec['segment'], spec['references']
    mode = mode or {'supports_audio': True}
    tag_template = mode.get('image_tag_template', '@图片{slot}')
    require(tag_template.count('{slot}') == 1 and '{' not in tag_template.replace('{slot}', '')
            and '}' not in tag_template.replace('{slot}', ''), 'unsupported image tag template')
    def render(value):
        return reference_text(value, references, tag_template)
    require(candidate.get('type') == 'video_prompt', 'expected video_prompt')
    require(candidate.get('schema_version') == '0.2.0', 'video_prompt schema_version must be 0.2.0')
    require(candidate.get('item') == spec['item'] and candidate.get('video_id') == segment['video_id'], 'candidate segment mismatch')
    require(candidate.get('duration_ms') == segment['generation_duration_ms'], 'prompt duration mismatch')
    require(candidate.get('mode') == segment['mode'], 'prompt mode mismatch')
    require(candidate.get('references') == references, 'prompt references differ from task bindings')
    require(text(candidate.get('global_setting')), 'prompt requires global_setting')
    require(text(candidate.get('audio')) and text(candidate.get('constraints')), 'prompt requires audio and constraints')
    # Deferred audio is still part of the handoff and must not hide invalid refs.
    render(candidate['audio'])
    timeline = candidate.get('timeline')
    require(isinstance(timeline, list) and len(timeline) == len(segment['timeline']), 'prompt timeline coverage mismatch')
    lines = ['素材声明：']
    for ref in references:
        lines.append(tag_template.format(slot=ref['planned_slot']) + f"：{ref['canonical_name']}；用途：{ref['role']}。")
    lines.extend(['', '全局设定：', render(candidate['global_setting']), '', '动作与镜头：'])
    for row, planned in zip(timeline, segment['timeline']):
        for key in ('local_start_ms', 'local_end_ms', 'span_id', 'padding_id'):
            require(row.get(key) == planned.get(key), f'prompt timeline {key} differs from production plan')
        require(text(row.get('action')) and text(row.get('camera')) and text(row.get('sound')), 'timeline requires action/camera/sound')
        render(row['sound'])
        caption = f"[{row['local_start_ms']/1000:g}—{row['local_end_ms']/1000:g}秒] "
        detail = row['action'] + '；镜头：' + row['camera']
        if mode['supports_audio']:
            detail += '；声音：' + row['sound']
        lines.append(caption + render(detail))
    def continuity(value):
        return value['state'] if isinstance(value, dict) else value
    if mode['supports_audio']:
        lines.extend(['', '声音：', render(candidate['audio'])])
    lines.extend(['', '约束：', render(candidate['constraints']), '',
                  '开场承接：' + continuity(segment['continuity_in']), '结束承接：' + continuity(segment['continuity_out'])])
    rendered = '\n'.join(lines) + '\n'
    if 'prompt' in candidate:
        require(candidate['prompt'] == rendered, 'rendered prompt differs from structured candidate')
    return dict(candidate, prompt=rendered, references=references,
                audio_delivery='native' if mode['supports_audio'] else 'postproduction')
