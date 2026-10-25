"""Portable export behavior, with deliberately synthetic artwork and writing."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from video_flow.contracts import FlowError
from video_flow.delivery import export_production_package
from video_flow.delivery_validation import MANIFEST_PATH, file_hash, verify_package


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / 'run'
        self.run.mkdir()
        self.output = self.root / 'package'
        self.config = {'board_max_panels': 4, 'delivery': {'text_encoding': 'utf-8-sig'}}
        self.artifacts = self.fixture()

    def image(self, key, stem, **extra):
        relative = 'media/' + key + '.png'
        path = self.run / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (16, 12), (35, 70, 90)).save(path)
        return {'item': key, 'file': relative, 'sha256': file_hash(path), 'revision': 1,
                'canonical_name': stem, 'width': 16, 'height': 12, 'format': 'png', **extra}

    def fixture(self):
        assets, media = [], []
        definitions = [('CHAR001', 'character', '甲'), ('CHAR002', 'character', '乙'),
                       ('SCENE001', 'space', '室内'), ('SCENE002', 'space', '室外'),
                       ('PROP001', 'prop', '台灯'), ('PROP002', 'prop', '钥匙')]
        for identity, kind, name in definitions:
            key = identity + '.default.front'
            assets.append({'id': identity, 'kind': kind, 'display_name': name,
                'states': [{'state_id': 'default'}],
                'media_requirements': [{'reference_key': key, 'state_id': 'default', 'view': 'front',
                                        'required': True, 'coverage_policy': 'independent'}]})
            media.append(self.image(key, identity + '_' + name + '_默认_正面_r001',
                                    reference_key=key, asset_id=identity, state_id='default', view='front'))
        scenes = []
        for index in range(1, 3):
            scenes.append({'id': f'SC{index:03d}', 'location': '测试地点', 'time': '夜间',
                'characters': [f'CHAR{index:03d}'], 'scene_goal': '完成交接', 'action': '人物拿起物品。',
                'duration_ms': 12000, 'dialogue': [{'speaker_id': f'CHAR{index:03d}', 'text': '原文台词。', 'delivery_note': ''}]})
        shots = []
        for index in range(1, 13):
            shots.append({'id': f'S{index:03d}', 'scene_id': f'SC{1 if index <= 6 else 2:03d}',
                'order': index, 'duration_ms': 2000, 'shot_size': '中景', 'camera_position': '平视',
                'primary_camera_motion': '固定', 'action': '人物伸手拿起物品。', 'start_state': '物品在桌上',
                'end_state': '物品在手中', 'axis': '保持轴线', 'cut_motivation': '动作衔接', 'lighting': '侧光',
                'sound': '环境声', 'asset_bindings': []})
        segments, boards, board_media, prompts = [], [], [], []
        for order in range(1, 5):
            video_id, board_id = f'V{order:03d}', f'SB{order:03d}'
            spans, timeline, panels = [], [], []
            for offset in range(3):
                shot_id = f'S{(order-1)*3+offset+1:03d}'
                span_id = video_id + '-' + shot_id
                spans.append({'span_id': span_id, 'shot_id': shot_id, 'source_start_ms': 0, 'source_end_ms': 2000})
                timeline.append({'span_id': span_id, 'local_start_ms': offset*2000, 'local_end_ms': (offset+1)*2000})
                panels.append({'panel_id': f'{board_id}-{offset+1}', 'span_id': span_id, 'source_time_ms': 0, 'frame_role': 'keyframe'})
            segment = {'video_id': video_id, 'order': order, 'mode': 'reference', 'source_spans': spans,
                       'generation_duration_ms': 6000, 'timeline': timeline, 'padding': [],
                       'continuity_in': '手在桌侧', 'continuity_out': '物品在手中', 'reference_keys': []}
            segments.append(segment)
            boards.append({'board_id': board_id, 'video_id': video_id, 'kind': 'panel_sheet',
                           'layout': 'ordered', 'reading_order': [p['panel_id'] for p in panels], 'panels': panels, 'reference_keys': []})
            board_row = self.image(board_id, board_id + '_r001')
            board_media.append(board_row)
            refs = []
            group = (0, 2, 4) if order <= 2 else (1, 3, 5)
            for slot, row in enumerate([media[i] for i in group] + [board_row], 1):
                refs.append({'reference_key': row.get('reference_key', row['item']), 'canonical_name': row['canonical_name'],
                             'file': row['file'], 'sha256': row['sha256'], 'planned_slot': slot, 'role': 'visual_reference'})
            prompts.append({'item': 'PROMPT-' + video_id, 'video_id': video_id, 'duration_ms': 6000,
                'mode': 'reference', 'timeline': copy.deepcopy(timeline), 'references': refs,
                'prompt': '素材声明：\n' + '\n'.join(ref['canonical_name'] for ref in refs) + '\n人物依次拿起物品。'})
        return {'story': {'items': scenes}, 'storyboard': {'items': shots}, 'assets': {'items': assets},
                'asset_media': {'items': media}, 'board_media': {'items': board_media},
                'production_plan': {'segments': segments, 'boards': boards}, 'video_prompts': {'items': prompts}}

    def export(self):
        return export_production_package(self.run, self.artifacts, self.output, self.config)

    def manifest(self):
        return json.loads((self.output / MANIFEST_PATH).read_text(encoding='utf-8'))

    def save_manifest(self, manifest):
        (self.output / MANIFEST_PATH).write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')

    def test_f01_portable_full_inventory_and_readable_text(self):
        result = self.export()
        report = verify_package(self.output)
        self.assertTrue(result['validation']['passed'])
        self.assertEqual(report['images_decoded'], 10)
        self.assertEqual(report['segments_checked'], 4)
        self.assertEqual(report['files_checked'], 21)
        self.assertIn('原文台词。', (self.output / '剧本.txt').read_text(encoding='utf-8-sig'))
        self.assertIn('主运镜：固定', (self.output / '详细分镜.txt').read_text(encoding='utf-8-sig'))
        self.assertEqual((self.output / '详细分镜.txt').read_text(encoding='utf-8-sig').count('镜号：'), 12)
        self.assertTrue((self.output / '剧本.txt').read_bytes().startswith(b'\xef\xbb\xbf'))
        moved = self.root / 'another-root' / 'copied'
        moved.parent.mkdir()
        shutil.copytree(self.output, moved)
        shutil.rmtree(self.run)
        self.assertTrue(verify_package(moved)['passed'])

    def test_deleted_renamed_and_tampered_files_fail_without_trusting_report(self):
        self.export()
        first = next(row for row in self.manifest()['files'] if row['role'] == 'asset_image')
        image = self.output / first['path']
        original = image.read_bytes()
        image.unlink()
        with self.assertRaisesRegex(FlowError, 'inventory'):
            verify_package(self.output)
        image.write_bytes(original)
        image.rename(image.with_name('renamed.png'))
        with self.assertRaisesRegex(FlowError, 'inventory'):
            verify_package(self.output)
        image.with_name('renamed.png').rename(image)
        image.write_bytes(original[:-1] + b'x')
        with self.assertRaisesRegex(FlowError, 'hash'):
            verify_package(self.output)

    def test_deferred_sound_is_delivered_in_mapping_with_resolved_names(self):
        for prompt in self.artifacts['video_prompts']['items']:
            key = prompt['references'][0]['reference_key']
            prompt['audio_delivery'] = 'postproduction'
            prompt['audio'] = '{{ref:' + key + '}}的脚步声。'
            for cue in prompt['timeline']:
                cue['sound'] = '脚步轻响'
        self.export()
        mapping = (self.output/'分镜板/V001/V001_参考图映射.txt').read_text(encoding='utf-8-sig')
        self.assertIn('后期声音交接', mapping)
        self.assertIn('脚步声', mapping)
        self.assertNotIn('{{ref:', mapping)

    def test_corrupt_image_rejected_even_if_manifest_hash_is_refreshed(self):
        self.export()
        manifest = self.manifest()
        row = next(row for row in manifest['files'] if row['role'] == 'asset_image')
        image = self.output / row['path']
        image.write_bytes(b'text disguised as png')
        row.update(size=image.stat().st_size, sha256=file_hash(image))
        self.save_manifest(manifest)
        with self.assertRaisesRegex(FlowError, 'decode'):
            verify_package(self.output)

    def test_source_corruption_and_missing_required_image_block_export(self):
        self.artifacts['asset_media']['items'].pop()
        with self.assertRaisesRegex(FlowError, 'missing required asset'):
            self.export()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('package.tmp-*')))

    def test_prompt_reference_old_revision_cannot_export(self):
        self.artifacts['video_prompts']['items'][0]['references'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(FlowError, 'unresolved reference'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_duplicate_slot_and_unknown_reference_names_are_rejected(self):
        self.artifacts['video_prompts']['items'][0]['references'][1]['planned_slot'] = 1
        with self.assertRaisesRegex(FlowError, 'upload slots'):
            self.export()

    def test_no_overwrite_and_copy_interruption_preserve_existing_outputs(self):
        self.export()
        before = (self.output / MANIFEST_PATH).read_bytes()
        with self.assertRaisesRegex(FlowError, 'already exists'):
            self.export()
        self.assertEqual((self.output / MANIFEST_PATH).read_bytes(), before)
        another = self.root / 'another'
        with patch('video_flow.delivery.shutil.copyfile', side_effect=OSError('injected copy failure')):
            with self.assertRaisesRegex(OSError, 'injected'):
                export_production_package(self.run, self.artifacts, another, self.config)
        self.assertFalse(another.exists())
        self.assertFalse(list(self.root.glob('another.tmp-*')))
        self.assertEqual((self.output / MANIFEST_PATH).read_bytes(), before)

    def test_timeline_gap_and_wrong_board_coverage_fail_independent_verifier(self):
        self.export()
        manifest = self.manifest()
        original = copy.deepcopy(manifest)
        manifest['segments'][0]['timeline'][1]['local_start_ms'] += 100
        self.save_manifest(manifest)
        with self.assertRaisesRegex(FlowError, 'gap/overlap'):
            verify_package(self.output)
        original['boards'][0]['panels'].pop()
        original['boards'][0]['reading_order'].pop()
        self.save_manifest(original)
        with self.assertRaisesRegex(FlowError, 'board coverage'):
            verify_package(self.output)

    def test_required_reference_omission_and_board_reordering_fail(self):
        self.export()
        manifest = self.manifest()
        original = copy.deepcopy(manifest)
        manifest['assets'][0]['references'] = []
        self.save_manifest(manifest)
        with self.assertRaisesRegex(FlowError, 'missing required asset reference'):
            verify_package(self.output)
        original['boards'][0]['panels'].reverse()
        original['boards'][0]['reading_order'].reverse()
        self.save_manifest(original)
        with self.assertRaisesRegex(FlowError, 'panel order changed'):
            verify_package(self.output)

    def test_unresolved_tokens_and_multigrid_first_frame_rejected(self):
        self.artifacts['video_prompts']['items'][0]['prompt'] += '{{ref:unknown}}'
        with self.assertRaisesRegex(FlowError, 'unresolved reference token'):
            self.export()
        self.artifacts['video_prompts']['items'][0]['prompt'] = self.artifacts['video_prompts']['items'][0]['prompt'].replace('{{ref:unknown}}', '')
        self.artifacts['video_prompts']['items'][0]['references'][-1]['role'] = 'first_frame'
        with self.assertRaisesRegex(FlowError, 'multi-panel'):
            self.export()

    def test_zero_character_and_prop_categories_are_explicit(self):
        self.artifacts['assets']['items'] = [a for a in self.artifacts['assets']['items'] if a['kind'] == 'space']
        self.artifacts['asset_media']['items'] = [r for r in self.artifacts['asset_media']['items'] if r['asset_id'].startswith('SCENE')]
        for prompt in self.artifacts['video_prompts']['items']:
            prompt['references'] = [r for r in prompt['references'] if r['reference_key'].startswith(('SCENE', 'SB'))]
            for slot, reference in enumerate(prompt['references'], 1):
                reference['planned_slot'] = slot
        self.export()
        manifest = self.manifest()
        self.assertEqual(manifest['asset_categories']['character'], {'count': 0, 'status': 'not_applicable'})
        self.assertEqual(list((self.output / '人物资产').iterdir()), [])
        self.assertEqual(list((self.output / '物品资产').iterdir()), [])

    def test_absolute_reference_path_and_unlisted_file_are_rejected(self):
        self.export()
        manifest = self.manifest()
        manifest['files'][0]['path'] = 'C:/private/file.png'
        self.save_manifest(manifest)
        with self.assertRaises(FlowError):
            verify_package(self.output)
        self.save_manifest(self.export_fresh_manifest())
        (self.output / 'extra.txt').write_text('unlisted', encoding='utf-8')
        with self.assertRaisesRegex(FlowError, 'inventory'):
            verify_package(self.output)

    def test_bundle_limits_are_checked_and_test_profiles_mark_synthetic(self):
        config = copy.deepcopy(self.config)
        config.update(media_mode='mock', selected_mode='reference')
        bundle = {'production': config, 'platform': {'profile_id': 'synthetic', 'status': 'test_only',
            'modes': {'reference': {'min_duration_ms': 4000, 'max_duration_ms': 10000,
                                    'max_images': 4, 'supports_multi_shot': True, 'supports_audio': False}}},
                  'provider': {'test_only': True}}
        result = export_production_package(self.run, self.artifacts, self.output, bundle)
        self.assertTrue(result['manifest']['synthetic'])
        self.assertEqual(result['manifest']['status'], 'synthetic_package_ready')
        self.assertTrue(result['validation']['platform_capacity_checked'])
        manifest = self.manifest()
        manifest['platform_profile']['limits']['max_images'] = 3
        self.save_manifest(manifest)
        with self.assertRaisesRegex(FlowError, 'exceed platform capacity'):
            verify_package(self.output)

    def export_fresh_manifest(self):
        other = self.root / 'fresh'
        return export_production_package(self.run, self.artifacts, other, self.config)['manifest']


if __name__ == '__main__':
    unittest.main()
