"""v0.2 contract failures are mechanical checks, not creative-quality proof."""
import json
from pathlib import Path
import tempfile
import unittest

import yaml

from video_flow.contracts import FlowError
from video_flow.profiles import (load_production_bundle, platform_profile_check,
                                 production_config_check, provider_profile_check)
from video_flow.registry import (canonical_filename, ensure_unique_names, registry_check,
                                 safe_name, safe_relative_file, story_check, storyboard_check)


def production():
    return {'schema_version': '0.2.0', 'profile_id': 'fixture', 'media_mode': 'mock',
            'selected_mode': 'reference', 'platform_profile': 'platform.yaml', 'provider_profile': 'provider.yaml',
            'board_max_panels': 4, 'max_concurrent_media': 1, 'repair_limit': 2,
            'delivery': {'text_encoding': 'utf-8-sig', 'directory_name': '{title}_制作包_r{revision:03d}'},
            'budget': {'paid_generation_authorized': False, 'max_total_cost': None, 'currency': 'USD'}}


def platform():
    return {'schema_version': '0.2.0', 'profile_id': 'fixture', 'status': 'test_only',
            'source': 'Synthetic test capability, not a real platform specification', 'verified_at': None,
            'modes': {'reference': {'min_duration_ms': 4000, 'max_duration_ms': 10000,
                                  'max_images': 8, 'supports_multi_shot': True, 'supports_audio': False}}}


def provider():
    return {'schema_version': '0.2.0', 'profile_id': 'fixture', 'status': 'test_only',
            'supports_reference_images': True, 'formats': ['png'], 'credential_env': None, 'test_only': True}


def asset():
    return {'id': 'CHAR001', 'kind': 'character', 'description': 'Synthetic person',
            'continuity_rules': 'Same uniform', 'display_name': '小林', 'invariant_features': ['短发'],
            'shot_ids': ['S001'], 'states': [{'state_id': 'work', 'description': '工作服', 'shot_ids': ['S001']}],
            'media_requirements': [{'reference_key': 'CHAR001.work.front', 'state_id': 'work',
                                    'view': 'front', 'required': True, 'coverage_policy': 'independent'}]}


def assets():
    return {'schema_version': '0.2.0', 'type': 'assets', 'items': [asset()]}


def story():
    return {'schema_version': '0.2.0', 'type': 'story', 'items': [{'id': 'SC001', 'scene_goal': 'Reveal',
            'action': 'Switch on a lamp', 'location': 'Office', 'time': 'Night', 'characters': ['CHAR001'],
            'dialogue': [], 'duration_ms': 4000}]}


def storyboard():
    row = {key: 'Synthetic fixture' for key in ('shot_size', 'camera_position', 'primary_camera_motion',
            'beat', 'action', 'start_state', 'end_state', 'axis', 'cut_motivation', 'lighting', 'sound')}
    row.update(id='S001', scene_id='SC001', order=1, duration_ms=4000,
               asset_bindings=[{'asset_id': 'CHAR001', 'state_id': 'work', 'purpose': 'Main actor',
                                'start_state': 'Seated', 'end_state': 'Standing'}])
    return {'schema_version': '0.2.0', 'type': 'storyboard', 'items': [row]}


class V02ContractsTests(unittest.TestCase):
    def test_names_are_nfc_and_windows_safe(self):
        self.assertEqual(safe_name('e\u0301'), 'é')
        self.assertEqual(canonical_filename('CHAR001', '小林', '工作服', '正面', 1), 'CHAR001_小林_工作服_正面_r001.png')
        for value in ('CON', 'con.png', 'COM¹.txt', 'x.', 'x ', 'a/b', 'a:b', '..', 'a\x00b', 'a'*256):
            with self.subTest(value=value), self.assertRaises(FlowError):
                safe_name(value)

    def test_names_reject_case_and_unicode_collisions(self):
        for pair in (['Test.png', 'test.png'], ['é.png', 'e\u0301.png']):
            with self.assertRaisesRegex(FlowError, 'collision'):
                ensure_unique_names(pair)

    def test_relative_path_rejects_windows_escapes(self):
        for value in ('C:asset.png', 'C:\\asset.png', '\\\\server\\share\\x.png', '../x.png', 'x/../y.png', '/x.png'):
            with self.subTest(value=value), self.assertRaises(FlowError):
                safe_relative_file(value)
        self.assertEqual(safe_relative_file('media\\人物.png'), 'media/人物.png')

    def test_profile_capabilities_are_finite_and_verified_is_evidenced(self):
        self.assertEqual(platform_profile_check(platform())['profile_id'], 'fixture')
        for change in ({'max_duration_ms': None}, {'max_images': None}, {'min_duration_ms': 11000}):
            value = platform()
            value['modes']['reference'].update(change)
            with self.assertRaises(FlowError):
                platform_profile_check(value)
        value = platform()
        value['status'] = 'verified'
        with self.assertRaisesRegex(FlowError, 'verification date'):
            platform_profile_check(value)

    def test_paid_generation_requires_finite_budget(self):
        value = production()
        value['media_mode'] = 'generate'
        value['budget']['paid_generation_authorized'] = True
        with self.assertRaisesRegex(FlowError, 'finite budget'):
            production_config_check(value)
        value['budget']['max_total_cost'] = 1
        production_config_check(value)
        value['budget']['max_total_cost'] = float('inf')
        with self.assertRaisesRegex(FlowError, 'finite'):
            production_config_check(value)

    def test_directory_template_and_verification_date_are_valid(self):
        for template in ('../{title}', '{title.__class__}', '{secret}', '{title!r}'):
            value=production()
            value['delivery']['directory_name']=template
            with self.subTest(template=template), self.assertRaises(FlowError):
                production_config_check(value)
        value=platform()
        value['verified_at']='2026-02-30'
        with self.assertRaisesRegex(FlowError,'calendar date'):
            platform_profile_check(value)

    def test_provider_accepts_env_name_not_key_value(self):
        value = provider()
        value['credential_env'] = 'IMAGE_API_KEY'
        provider_profile_check(value)
        value['credential_env'] = 'sk-secret-with-dashes'
        with self.assertRaisesRegex(FlowError, 'environment variable name'):
            provider_profile_check(value)

    def test_bundle_is_confined_and_mode_is_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def put(name, value):
                (root/name).write_text(yaml.safe_dump(value, allow_unicode=True), encoding='utf-8')
            put('platform.yaml', platform())
            put('provider.yaml', provider())
            value = production()
            put('production.yaml', value)
            self.assertEqual(set(load_production_bundle(root/'production.yaml')), {'production','platform','provider'})
            for change in ({'platform_profile':'../platform.yaml'}, {'selected_mode':'unknown'},
                           {'target_segment_duration_ms':3000}, {'media_mode':'import'}):
                changed = dict(value, **change)
                put('production.yaml', changed)
                with self.assertRaises(FlowError):
                    load_production_bundle(root/'production.yaml')

    def test_registry_requires_states_and_independent_media(self):
        data=assets()
        self.assertEqual(set(registry_check(data, shot_ids=['S001'])), {'CHAR001.work.front'})
        with self.assertRaisesRegex(FlowError, 'missing required'):
            registry_check(data, {'items':[]})
        data['items'][0]['media_requirements'][0]['state_id']='missing'
        with self.assertRaisesRegex(FlowError, 'unknown state'):
            registry_check(data)

    def test_required_scene_coverage_requires_actual_scene_media(self):
        data=assets()
        space=data['items'][0]
        space.update(id='SPACE001',kind='space')
        space['media_requirements'][0].update(reference_key='SPACE001.work.front',required=False)
        prop=asset()
        prop.update(id='PROP001',kind='prop')
        prop['media_requirements'][0].update(reference_key='PROP001.work.front',coverage_policy='scene_reference',
                                            covered_by_reference_key='SPACE001.work.front')
        data['items'].append(prop)
        with self.assertRaisesRegex(FlowError,'missing required references: SPACE001.work.front'):
            registry_check(data,{'items':[]})
        prop['interaction_critical']=True
        with self.assertRaisesRegex(FlowError,'interaction-critical'):
            registry_check(data)

    def test_registry_rejects_unknown_duplicate_and_mismatched_media(self):
        filename=canonical_filename('CHAR001','小林','work','front',1)
        row={'reference_key':'CHAR001.work.front','media_id':'M1','revision':1,'canonical_name':Path(filename).stem,
             'file':'media/'+filename,'sha256':'a'*64,'width':100,'height':100,'format':'png','source':'mock',
             'review_ref':{'path':'reviews/review.json','sha256':'b'*64}}
        registry_check(assets(),{'items':[row]})
        for change in ({'reference_key':'UNKNOWN'}, {'canonical_name':'wrong'}, {'file':'../x.png'}):
            with self.assertRaises(FlowError):
                registry_check(assets(), {'items':[dict(row,**change)]})
        with self.assertRaisesRegex(FlowError, 'duplicate'):
            registry_check(assets(), {'items':[row,row]})

    def test_storyboard_detailed_fields_and_duration(self):
        inputs={'brief':{'duration_seconds':4},'story':story(),'assets':assets()}
        storyboard_check(storyboard(),inputs)
        for field in ('shot_size','lighting','asset_bindings'):
            value=storyboard()
            del value['items'][0][field]
            with self.assertRaisesRegex(FlowError,field):
                storyboard_check(value,inputs)
        value=storyboard()
        value['items'][0]['duration_ms']=-1
        with self.assertRaises(FlowError):
            storyboard_check(value,inputs)
        value=storyboard()
        value['items'][0]['duration_seconds']=4
        with self.assertRaisesRegex(FlowError,'duration_ms only'):
            storyboard_check(value,inputs)

    def test_story_requires_exact_time_and_dialogue_fields(self):
        story_check(story(), {'brief':{'duration_ms':4000}})
        value=story()
        value['items'][0]['dialogue']=[{'speaker_id':'CHAR001','text':'原文'}]
        with self.assertRaisesRegex(FlowError,'delivery_note'):
            story_check(value,{'brief':{'duration_ms':4000}})
        with self.assertRaisesRegex(FlowError,'total'):
            story_check(story(),{'brief':{'duration_ms':4001}})

    def test_all_v02_schema_files_are_valid_json_schema(self):
        from jsonschema import Draft202012Validator
        from video_flow.profiles import SCHEMA_ROOT
        for path in SCHEMA_ROOT.glob('*.json'):
            with self.subTest(path=path.name):
                Draft202012Validator.check_schema(json.loads(path.read_text(encoding='utf-8')))


if __name__ == '__main__':
    unittest.main()
