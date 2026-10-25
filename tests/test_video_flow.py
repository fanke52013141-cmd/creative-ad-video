"""Protocol behavior: synthetic actors/outputs do not certify creative quality."""
from pathlib import Path
import copy
import json
import shutil
import sys
import tempfile
import unittest

from video_flow import engine
from video_flow.contracts import FlowError
from video_flow.storage import digest, read, write

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from sequence_review_gate import check_sequence_review

BRIEF = {'title': 'Synthetic coffee', 'goal': 'brand', 'narrative_form': 'standalone',
         'distribution': 'vertical', 'duration_seconds': 30, 'episode_count': 1,
         'production_mode': 'generative', 'style': 'realism', 'constraints': ['Fictional brand'], 'facts': []}


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'standard'
        (self.root / 'config').mkdir(parents=True)
        for name in ('workflow.yaml', 'routes.yaml'):
            shutil.copyfile(ROOT / 'config' / name, self.root / 'config' / name)
        # Protocol tests isolate skill contents from concurrent authoring/research.
        stages = engine.load_yaml(self.root / 'config/workflow.yaml')['stages']
        names = {x['skill'] for x in stages} - {'$writer'}
        for x in stages:
            names.update((x.get('fanout') or {}).get('skill_by_kind', {}).values())
        for name in names | {'script-ad', 'script-shortfilm'}:
            path = self.root / '.agents/skills' / name / 'SKILL.md'
            path.parent.mkdir(parents=True)
            path.write_text('Synthetic test skill: ' + name, encoding='utf-8')
        self.run = Path(self.temp.name) / 'run'
        engine.initialize(self.run, copy.deepcopy(BRIEF), 'automatic', self.root)

    def dispatch(self, stage, actor=None):
        packet = engine.dispatch(self.run, stage)
        engine.bind(self.run, packet['task_id'], actor or stage + '-agent')
        return packet

    def put(self, packet, candidate):
        candidate['task_id'] = packet['task_id']
        base = Path(packet['output_root'])
        write(base / 'candidate.json', candidate)
        state = read(self.run / 'checkpoint.json')
        write(base / 'receipt.json', {'task_id': packet['task_id'], 'agent_id': state['tasks'][packet['task_id']]['agent_id'],
                'skill_sha256': packet['skill_sha256'], 'input_hashes': packet['input_hashes'], 'output_sha256': digest(base / 'candidate.json')})

    def story(self):
        packet = self.dispatch('story')
        self.put(packet, {'type': 'story', 'items': [{'id': 'SC001', 'scene_goal': 'recognition', 'action': 'A person shares coffee', 'duration_seconds': 30}]})
        engine.submit(self.run, packet['task_id'])
        return packet

    def review(self, stage, verdict='pass'):
        packet = self.dispatch(stage)
        target = packet['review_target']
        self.put(packet, {'type': 'review', 'target_sha256': packet['input_hashes'][target], 'verdict': verdict,
            'coverage': [x['id'] for x in packet['inputs'][target]['items']], 'issues': [],
            'criteria': [{'name': name, 'score': 3, 'evidence': 'Test fixture; not creative certification'} for name in packet['review_criteria']]})
        engine.submit(self.run, packet['task_id'])
        return packet

    def test_order_and_minimal_context(self):
        self.assertEqual(engine.status(self.run)['ready'], ['story'])
        with self.assertRaises(FlowError):
            engine.dispatch(self.run, 'style')
        packet = self.dispatch('story')
        self.assertEqual(set(packet['inputs']), {'brief', 'route'})
        self.assertNotIn('history', packet)
        self.assertEqual(packet['context_mode'], 'fresh')

    def test_route_only_where_a_criterion_needs_it(self):
        self.story()
        review_packet = self.dispatch('story_review')
        self.assertIn('route', review_packet['inputs'])  # route_fit criterion needs it
        self.put(review_packet, {'type': 'review', 'target_sha256': review_packet['input_hashes']['story'],
            'verdict': 'pass', 'coverage': ['SC001'], 'issues': [],
            'criteria': [{'name': name, 'score': 3, 'evidence': 'Test fixture; not creative certification'} for name in review_packet['review_criteria']]})
        engine.submit(self.run, review_packet['task_id'])
        style_packet = self.dispatch('style')
        self.assertNotIn('route', style_packet['inputs'])  # creators do not get routing duplicates

    def test_route_overlap_and_unsupported_types(self):
        rules = engine.load_yaml(self.root / 'config/routes.yaml')
        brief = copy.deepcopy(BRIEF)
        self.assertEqual(engine.resolve_route(brief, rules)['writer'], 'script-ad')
        brief['goal'] = 'art'
        self.assertEqual(engine.resolve_route(brief, rules)['writer'], 'script-shortfilm')
        for change in ({'episode_count': 6}, {'narrative_form': 'serial'}, {'narrative_form': 'documentary'}, {'style': 'unbuilt'}):
            other = dict(brief, **change)
            with self.assertRaises(FlowError):
                engine.resolve_route(other, rules)

    def test_cannot_complete_without_bound_task(self):
        packet = engine.dispatch(self.run, 'story')
        with self.assertRaisesRegex(FlowError, 'bound'):
            engine.submit(self.run, packet['task_id'])
        with self.assertRaises(FlowError):
            engine.submit(self.run, 'invented-task')

    def test_input_tamper_blocks_progress(self):
        self.story()
        write(self.run / 'inputs/brief.json', dict(BRIEF, title='tampered'))
        with self.assertRaisesRegex(FlowError, 'hash mismatch'):
            engine.dispatch(self.run, 'story_review')

    def test_skill_snapshot_cannot_change_during_task(self):
        packet = self.dispatch('story')
        (self.run / 'standard/skills/script-ad/SKILL.md').write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(FlowError, 'skill changed'):
            engine.submit(self.run, packet['task_id'])

    def test_independent_reviewer_required(self):
        self.story()
        task = engine.dispatch(self.run, 'story_review')
        with self.assertRaisesRegex(FlowError, 'differ'):
            engine.bind(self.run, task['task_id'], 'story-agent')

    def test_pass_label_does_not_override_serious_issues(self):
        self.story()
        packet = self.dispatch('story_review')
        self.put(packet, {'type': 'review', 'target_sha256': packet['input_hashes']['story'], 'verdict': 'pass',
            'coverage': ['SC001'], 'issues': [{'severity': 'P0', 'location': 'SC001', 'reason': 'contradiction'}],
            'criteria': [{'name': 'causality', 'score': 4, 'evidence': 'SC001'}]})
        with self.assertRaisesRegex(FlowError, 'P0/P1'):
            engine.submit(self.run, packet['task_id'])

    def test_empty_review_coverage_blocks(self):
        self.story()
        packet = self.dispatch('story_review')
        self.put(packet, {'type': 'review', 'target_sha256': packet['input_hashes']['story'], 'verdict': 'pass',
            'coverage': [], 'issues': [], 'criteria': [{'name': 'causality', 'score': 4, 'evidence': 'SC001'}]})
        with self.assertRaisesRegex(FlowError, 'cover exactly'):
            engine.submit(self.run, packet['task_id'])

    def test_approval_is_separate_from_quality(self):
        with (self.run / 'checkpoint.json').open(encoding='utf-8') as stream:
            state = json.load(stream)
        state['approval_policy'] = 'key_decisions'
        write(self.run / 'checkpoint.json', state)
        self.story()
        self.review('story_review')
        self.assertEqual(engine.status(self.run)['ready'], [])
        self.assertEqual(engine.status(self.run)['stages']['story']['status'], 'quality_passed')
        engine.approve(self.run, 'story_review', 'synthetic-user', 'fixture approval')
        self.assertEqual(engine.status(self.run)['ready'], ['style'])

    def test_repair_feedback_and_stale_result(self):
        old = self.story()
        self.review('story_review', 'revise')
        packet = self.dispatch('story')
        self.assertIn('repair_feedback', packet)
        with self.assertRaisesRegex(FlowError, 'stale task'):
            engine.submit(self.run, old['task_id'])
        self.assertEqual(engine.status(self.run)['stages']['story_review']['status'], 'pending')

    def test_retry_is_bounded_and_late_result_rejected(self):
        task = self.dispatch('story')
        for i in range(3):
            engine.retry(self.run, task['task_id'], 'synthetic tool failure')
            if i < 2:
                task = self.dispatch('story', f'worker-{i}')
        with self.assertRaisesRegex(FlowError, 'budget'):
            engine.dispatch(self.run, 'story')
        with self.assertRaises(FlowError):
            engine.submit(self.run, task['task_id'])

    def test_packet_tampering_rejected(self):
        packet = self.dispatch('story')
        path = self.run / 'tasks' / (packet['task_id'] + '.json')
        write(path, dict(packet, skill='wrong-skill'))
        with self.assertRaisesRegex(FlowError, 'packet hash'):
            engine.submit(self.run, packet['task_id'])

    def test_receipt_hash_and_duplicate_submit(self):
        packet = self.dispatch('story')
        self.put(packet, {'type': 'story', 'items': [{'id': 'SC001', 'scene_goal': 'one', 'action': 'two', 'duration_seconds': 30}]})
        path = Path(packet['output_root']) / 'receipt.json'
        receipt = read(path)
        write(path, dict(receipt, output_sha256='wrong'))
        with self.assertRaisesRegex(FlowError, 'output hash'):
            engine.submit(self.run, packet['task_id'])
        write(path, receipt)
        engine.submit(self.run, packet['task_id'])
        with self.assertRaises(FlowError):
            engine.submit(self.run, packet['task_id'])

    def test_full_synthetic_delivery_and_invalidation(self):
        self.story()
        self.review('story_review')
        candidates = {
            'style': {'type': 'style', 'items': [{'id': 'LIGHT', 'axis': 'lighting', 'rule': 'window key light', 'story_reason': 'clarity'}]},
            'storyboard': {'type': 'storyboard', 'items': [{'id': 'S001', 'scene_id': 'SC001', 'beat': 'share', 'action': 'share coffee', 'start_state': 'separate cups', 'end_state': 'shared table', 'duration_seconds': 30, 'axis': 'camera south', 'cut_motivation': 'scene complete', 'sound': 'room tone'}]},
            'assets': {'type': 'assets', 'items': [{'id': 'CUP', 'kind': 'prop', 'description': 'coffee cup', 'shot_ids': ['S001'], 'continuity_rules': 'same cup'}]},
            'edit_sound': {'type': 'edit_sound', 'items': [{'id': 'ED001', 'shot_id': 'S001', 'picture_cut': 'end', 'sound': 'room tone', 'motivation': 'leave on response'}]}}
        for stage, candidate in candidates.items():
            packet = self.dispatch(stage)
            self.put(packet, candidate)
            engine.submit(self.run, packet['task_id'])
            self.review(stage + '_review')
        package = engine.package(self.run)
        manifest = read(Path(package['package']) / 'manifest.json')
        self.assertEqual(manifest['delivery_level'], 'preproduction_text')
        for ref in manifest['files']:
            self.assertEqual(digest(Path(package['package']) / ref['path']), ref['sha256'])
        engine.invalidate(self.run, 'story_review', 'new story request')
        with self.assertRaises(FlowError):
            engine.package(self.run)
        self.assertEqual(engine.status(self.run)['ready'], ['story'])

    def test_package_and_concurrent_dispatch_fail_closed(self):
        with self.assertRaises(FlowError):
            engine.package(self.run)
        (self.run / '.flow.lock').write_text('test-process', encoding='utf-8')
        with self.assertRaisesRegex(FlowError, 'locked'):
            engine.dispatch(self.run, 'story')


class MediaFanoutTests(unittest.TestCase):
    """Fanout media stages: one bounded task per item, minimal packets, item-scoped repair."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'standard'
        (self.root / 'config').mkdir(parents=True)
        for name in ('workflow.yaml', 'routes.yaml'):
            shutil.copyfile(ROOT / 'config' / name, self.root / 'config' / name)
        stages = engine.load_yaml(self.root / 'config/workflow.yaml')['stages']
        names = {x['skill'] for x in stages} - {'$writer'}
        for x in stages:
            names.update((x.get('fanout') or {}).get('skill_by_kind', {}).values())
        for name in names | {'script-ad', 'script-shortfilm'}:
            path = self.root / '.agents/skills' / name / 'SKILL.md'
            path.parent.mkdir(parents=True)
            path.write_text('Synthetic test skill: ' + name, encoding='utf-8')
        self.run = Path(self.temp.name) / 'run'
        engine.initialize(self.run, copy.deepcopy(BRIEF), 'automatic', media=True, root=self.root)

    def dispatch(self, stage, actor=None, item=None):
        packet = engine.dispatch(self.run, stage, item)
        engine.bind(self.run, packet['task_id'], actor or (stage + '-' + str(item) + '-agent'))
        return packet

    def put(self, packet, candidate):
        candidate['task_id'] = packet['task_id']
        base = Path(packet['output_root'])
        write(base / 'candidate.json', candidate)
        state = read(self.run / 'checkpoint.json')
        write(base / 'receipt.json', {'task_id': packet['task_id'], 'agent_id': state['tasks'][packet['task_id']]['agent_id'],
                'skill_sha256': packet['skill_sha256'], 'input_hashes': packet['input_hashes'], 'output_sha256': digest(base / 'candidate.json')})

    def review(self, stage, verdict='pass', issues=None):
        packet = self.dispatch(stage)
        target = packet['review_target']
        self.put(packet, {'type': 'review', 'target_sha256': packet['input_hashes'][target], 'verdict': verdict,
            'coverage': [x.get('id') or x.get('item') for x in packet['inputs'][target]['items']],
            'issues': issues or [],
            'criteria': [{'name': name, 'score': 3, 'evidence': 'Test fixture; not creative certification'} for name in packet['review_criteria']]})
        return engine.submit(self.run, packet['task_id'])

    def text_flow(self):
        packet = self.dispatch('story')
        self.put(packet, {'type': 'story', 'items': [{'id': 'SC001', 'scene_goal': 'recognition', 'action': 'A person shares coffee', 'duration_seconds': 30}]})
        engine.submit(self.run, packet['task_id'])
        self.review('story_review')
        candidates = {
            'style': {'type': 'style', 'items': [{'id': 'LIGHT', 'axis': 'lighting', 'rule': 'window key light', 'story_reason': 'clarity'}]},
            'storyboard': {'type': 'storyboard', 'items': [{'id': 'S001', 'scene_id': 'SC001', 'beat': 'share', 'action': 'share coffee', 'start_state': 'separate cups', 'end_state': 'shared table', 'duration_seconds': 30, 'axis': 'camera south', 'cut_motivation': 'scene complete', 'sound': 'room tone'}]},
            'assets': {'type': 'assets', 'items': [
                {'id': 'CHAR-1', 'kind': 'character', 'description': 'shop owner', 'shot_ids': ['S001'], 'continuity_rules': 'same person', 'invariant_features': 'grey hair; rolled sleeves'},
                {'id': 'SPACE-1', 'kind': 'space', 'description': 'the shop', 'shot_ids': ['S001'], 'continuity_rules': 'one room'},
                {'id': 'CUP', 'kind': 'prop', 'description': 'coffee cup', 'shot_ids': ['S001'], 'continuity_rules': 'same cup'}]},
            'edit_sound': {'type': 'edit_sound', 'items': [{'id': 'ED001', 'shot_id': 'S001', 'picture_cut': 'end', 'sound': 'room tone', 'motivation': 'leave on response'}]}}
        for stage, candidate in candidates.items():
            packet = self.dispatch(stage)
            self.put(packet, candidate)
            engine.submit(self.run, packet['task_id'])
            self.review(stage + '_review')

    def media_item(self, stage, item):
        packet = self.dispatch(stage, item=item)
        image = self.run / packet['fanout']['target_file']
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b'synthetic-image:' + item.encode())
        self.put(packet, {'type': 'media_item', 'item': item, 'file': packet['fanout']['target_file'],
                          'sha256': digest(image), 'prompt': 'synthetic prompt ' + item, 'model': 'synthetic', 'quality': 'low'})
        return engine.submit(self.run, packet['task_id']), packet

    def test_media_profile_selects_stages_and_delivery_level(self):
        self.assertIn('asset_media', engine.status(self.run)['stages'])
        text_only = Path(self.temp.name) / 'run-text'
        engine.initialize(text_only, copy.deepcopy(BRIEF), 'automatic', root=self.root)
        self.assertNotIn('asset_media', engine.status(text_only)['stages'])
        self.assertEqual(read(text_only / 'standard/workflow.json')['delivery_level'], 'preproduction_text')

    def test_fanout_queue_and_minimal_packet(self):
        self.text_flow()
        with self.assertRaisesRegex(FlowError, 'requires an item id'):
            engine.dispatch(self.run, 'asset_media')
        with self.assertRaisesRegex(FlowError, 'unknown fanout item'):
            engine.dispatch(self.run, 'asset_media', 'CUP')  # prop kind is not selected
        packet = engine.dispatch(self.run, 'asset_media', 'CHAR-1')
        sliced = packet['inputs']['assets']
        self.assertEqual(sliced['item'], 'CHAR-1')  # single item spec, never the whole artifact
        self.assertEqual(packet['artifact_type'], 'media_item')
        self.assertTrue(packet['fanout']['target_file'].startswith('media/asset_media/CHAR-1'))
        self.assertEqual(packet['fanout']['size'], '1024x1536')
        boards = engine.dispatch(self.run, 'board_media', 'BOARD-SC001')
        self.assertEqual(len(boards['inputs']['storyboard']['shots']), 1)

    def video_prompt_item(self):
        packet = self.dispatch('video_prompts', item='PROMPT-S001')
        self.put(packet, {'type': 'video_prompt', 'item': 'PROMPT-S001', 'shot_id': 'S001',
                          'prompt': 'synthetic shot prompt', 'camera': 'static', 'sound': 'room tone'})
        return engine.submit(self.run, packet['task_id'])

    def test_media_flow_assembles_packages_and_hashes(self):
        self.text_flow()
        self.media_item('asset_media', 'CHAR-1')
        stages = engine.status(self.run)['stages']
        self.assertEqual(stages['asset_media']['status'], 'in_progress')
        self.assertEqual(stages['asset_media']['items_pending'], ['SPACE-1'])
        self.media_item('asset_media', 'SPACE-1')
        self.assertEqual(engine.status(self.run)['stages']['asset_media']['status'], 'submitted')
        self.review('asset_media_review')
        self.media_item('board_media', 'BOARD-SC001')
        self.review('board_media_review')
        self.video_prompt_item()
        self.review('video_prompts_review')
        package = engine.package(self.run)
        manifest = read(Path(package['package']) / 'manifest.json')
        self.assertEqual(manifest['delivery_level'], 'preproduction_text_and_reference_media')
        media_files = [f for f in manifest['files'] if f['path'].startswith('media/')]
        self.assertEqual(len(media_files), 3)
        self.assertEqual(len([f for f in manifest['files'] if f['artifact'] == 'video_prompts']), 1)
        for ref in manifest['files']:
            self.assertEqual(digest(Path(package['package']) / ref['path']), ref['sha256'])

    def test_media_item_rejects_wrong_hash_and_wrong_file(self):
        self.text_flow()
        packet = self.dispatch('asset_media', item='CHAR-1')
        image = self.run / packet['fanout']['target_file']
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b'synthetic-image')
        self.put(packet, {'type': 'media_item', 'item': 'CHAR-1', 'file': packet['fanout']['target_file'],
                          'sha256': '0' * 64, 'prompt': 'synthetic'})
        with self.assertRaisesRegex(FlowError, 'media file hash'):
            engine.submit(self.run, packet['task_id'])
        tampered = dict(packet)
        self.put(tampered, {'type': 'media_item', 'item': 'CHAR-1', 'file': 'media/asset_media/OTHER.png',
                            'sha256': digest(image), 'prompt': 'synthetic'})
        with self.assertRaisesRegex(FlowError, 'target file'):
            engine.submit(self.run, packet['task_id'])

    def test_media_review_revise_reopens_only_cited_items(self):
        self.text_flow()
        self.media_item('asset_media', 'CHAR-1')
        self.media_item('asset_media', 'SPACE-1')
        self.review('asset_media_review', 'revise',
                    issues=[{'severity': 'P1', 'location': 'item CHAR-1 prompt', 'reason': 'fixture revision'}])
        stages = engine.status(self.run)['stages']
        self.assertEqual(stages['asset_media']['status'], 'in_progress')
        self.assertEqual(stages['asset_media']['items_pending'], ['CHAR-1'])
        self.assertEqual(stages['asset_media']['items_done'], ['SPACE-1'])  # sibling keeps its result
        packet = engine.dispatch(self.run, 'asset_media', 'CHAR-1')
        self.assertIn('repair_feedback', packet)
        self.assertEqual(packet['repair_feedback']['issues'][0]['location'], 'item CHAR-1 prompt')

    def test_skill_by_kind_routing(self):
        self.text_flow()
        packet = self.dispatch('asset_media', item='CHAR-1')
        self.assertEqual(packet['skill'], 'character-visual-design')
        sliced = packet['inputs']['assets']
        self.assertEqual(sliced['invariant_features'], 'grey hair; rolled sleeves')  # full record, anchors ride along
        board = self.dispatch('board_media', item='BOARD-SC001')
        self.assertEqual(board['skill'], 'storyboard-panel-prompts')
        space = self.dispatch('asset_media', item='SPACE-1')
        self.assertEqual(space['skill'], 'scene-visual-design')

    def test_video_prompt_text_fanout(self):
        self.text_flow()
        self.media_item('asset_media', 'CHAR-1')
        self.media_item('asset_media', 'SPACE-1')
        self.review('asset_media_review')
        self.media_item('board_media', 'BOARD-SC001')
        self.review('board_media_review')
        packet = self.dispatch('video_prompts', item='PROMPT-S001')
        self.assertEqual(packet['skill'], 'video-shot-prompts')
        self.assertEqual(packet['artifact_type'], 'video_prompt')
        self.assertEqual(packet['fanout']['shot_id'], 'S001')
        self.assertNotIn('target_file', packet['fanout'])
        # minimal per-shot slices, never sibling shots
        self.assertEqual(packet['inputs']['storyboard']['shot']['id'], 'S001')
        self.assertEqual([x['shot_id'] for x in packet['inputs']['edit_sound']['items']], ['S001'])
        self.assertEqual([x['item'] for x in packet['inputs']['board_media']['items']], ['BOARD-SC001'])
        self.put(packet, {'type': 'video_prompt', 'item': 'PROMPT-S001', 'shot_id': 'S001',
                          'prompt': 'synthetic shot prompt', 'camera': 'static', 'sound': 'room tone'})
        stages = engine.submit(self.run, packet['task_id'])['stages']
        self.assertEqual(stages['video_prompts']['status'], 'submitted')
        self.review('video_prompts_review')
        assembled = read(self.run / next(iter(
            f"artifacts/video_prompts/{r['path'].split('/')[-1]}"
            for r in [read(self.run / 'checkpoint.json')['artifacts']['video_prompts']])))
        self.assertEqual(assembled['type'], 'fanout_set')
        self.assertEqual(len(assembled['items']), 1)
        package = engine.package(self.run)
        manifest = read(Path(package['package']) / 'manifest.json')
        prompts = [f for f in manifest['files'] if f['artifact'] == 'video_prompts']
        self.assertEqual(len(prompts), 1)

    def test_invalidate_single_item(self):
        self.text_flow()
        self.media_item('asset_media', 'CHAR-1')
        self.media_item('asset_media', 'SPACE-1')
        self.review('asset_media_review')
        engine.invalidate(self.run, 'asset_media', 'regenerate the character', item='CHAR-1')
        stages = engine.status(self.run)['stages']
        self.assertEqual(stages['asset_media']['items_pending'], ['CHAR-1'])
        self.assertEqual(stages['asset_media']['items_done'], ['SPACE-1'])
        self.assertEqual(stages['asset_media_review']['status'], 'pending')


class LegacyReviewRegression(unittest.TestCase):
    def test_pass_with_p0_is_rejected(self):
        with self.assertRaises(ValueError):
            check_sequence_review({'status': 'pass', 'checked_shots': ['S001'], 'issues': [{'severity': 'P0'}]}, {'shots': [{'shot_id': 'S001'}]})

    def test_pass_with_empty_or_missing_shots_is_rejected(self):
        for shots in ([], ['S002'], ['S001', 'S001']):
            with self.assertRaises(ValueError):
                check_sequence_review({'status': 'pass', 'checked_shots': shots, 'issues': []}, {'shots': [{'shot_id': 'S001'}]})


if __name__ == '__main__':
    unittest.main()
