"""Synthetic planning cases; no media or platform behavior is certified here."""
import copy
import unittest

from video_flow.contracts import FlowError
from video_flow.production_plan import build_production_plan, validate_production_plan


PROFILE = {'min_duration_ms':4000, 'max_duration_ms':10000,
           'supports_multi_shot':True, 'mode':'reference'}


def storyboard(count=12, duration=2000, scene_size=6):
    return {'items':[{'id':f'S{i:03d}', 'scene_id':f'SC{(i-1)//scene_size+1:03d}',
                      'order':i, 'duration_ms':duration, 'action':f'action {i}',
                      'start_state':f'start {i}', 'end_state':f'end {i}',
                      'reference_keys':['CHAR001.work.front']}
                     for i in range(1,count+1)]}


class ProductionPlanningTests(unittest.TestCase):
    def test_f01_exact_twelve_shot_coverage(self):
        data=storyboard()
        plan=build_production_plan(data, PROFILE, target_duration_ms=6000)
        self.assertEqual([s['generation_duration_ms'] for s in plan['segments']], [6000]*4)
        self.assertEqual([len(s['source_spans']) for s in plan['segments']], [3]*4)
        self.assertEqual([len(b['panels']) for b in plan['boards']], [3]*4)
        self.assertEqual([s['shot_id'] for v in plan['segments'] for s in v['source_spans']],
                         [s['id'] for s in data['items']])
        self.assertEqual(validate_production_plan(plan,data,PROFILE),plan)

    def test_f03_five_shots_in_one_segment_are_four_plus_one_panels(self):
        plan=build_production_plan(storyboard(5,1000), PROFILE)
        self.assertEqual(len(plan['segments']),1)
        self.assertEqual([len(b['panels']) for b in plan['boards']], [4,1])

    def test_scene_boundary_never_merged_even_if_below_minimum(self):
        plan=build_production_plan(storyboard(2,1000,1), PROFILE)
        self.assertEqual(len(plan['segments']),2)
        self.assertEqual([s['padding'][0]['duration_ms'] for s in plan['segments']],[3000,3000])
        self.assertEqual(sum(span['source_end_ms']-span['source_start_ms'] for seg in plan['segments']
                             for span in seg['source_spans']),2000)

    def test_short_isolated_shot_padding_must_be_explicit(self):
        data=storyboard(1,2000)
        with self.assertRaisesRegex(FlowError,'padding disabled'):
            build_production_plan(data,PROFILE,allow_padding=False)

    def test_long_shot_splits_only_on_explicit_boundaries(self):
        data=storyboard(1,22000)
        with self.assertRaisesRegex(FlowError,'needs_input'):
            build_production_plan(data,PROFILE)
        data['items'][0]['split_points_ms']=[8000,16000]
        plan=build_production_plan(data,PROFILE)
        self.assertEqual([(s['source_start_ms'],s['source_end_ms']) for v in plan['segments']
                          for s in v['source_spans']],[(0,8000),(8000,16000),(16000,22000)])
        self.assertEqual(plan['segments'][0]['continuity_out']['state'],'')
        self.assertEqual(plan['segments'][1]['continuity_in']['state'],'')
        data['items'][0]['split_states']={'8000':'hand reaches door'}
        with_states=build_production_plan(data,PROFILE)
        self.assertEqual(with_states['segments'][0]['continuity_out']['state'],'hand reaches door')
        self.assertEqual(with_states['segments'][1]['continuity_in']['state'],'hand reaches door')
        data['items'][0]['split_points_ms']=[11000]
        with self.assertRaisesRegex(FlowError,'no usable split'):
            build_production_plan(data,PROFILE)

    def test_single_shot_profile_does_not_merge(self):
        profile=dict(PROFILE,supports_multi_shot=False)
        plan=build_production_plan(storyboard(3,2000),profile)
        self.assertEqual(len(plan['segments']),3)
        self.assertTrue(all(len(v['source_spans'])==1 for v in plan['segments']))

    def test_unknown_capability_and_invalid_integer_time_are_rejected(self):
        for profile in ({},dict(PROFILE,max_duration_ms=None),dict(PROFILE,supports_multi_shot=None)):
            with self.assertRaises(FlowError):
                build_production_plan(storyboard(),profile)
        for duration in (True,0,-1,2000.5):
            with self.assertRaises(FlowError):
                build_production_plan(storyboard(1,duration),PROFILE)

    def test_validation_rejects_timeline_gap_and_overlap(self):
        data=storyboard()
        original=build_production_plan(data,PROFILE,target_duration_ms=6000)
        for delta in (-100,100):
            plan=copy.deepcopy(original)
            plan['segments'][0]['timeline'][1]['local_start_ms']+=delta
            with self.assertRaisesRegex(FlowError,'gap/overlap'):
                validate_production_plan(plan,data,PROFILE)

    def test_validation_rejects_missing_source_and_wrong_panel(self):
        data=storyboard()
        original=build_production_plan(data,PROFILE,target_duration_ms=6000)
        plan=copy.deepcopy(original)
        plan['boards'].pop()
        with self.assertRaisesRegex(FlowError,'cover every'):
            validate_production_plan(plan,data,PROFILE)
        plan=copy.deepcopy(original)
        plan['boards'][0]['panels'][0]['span_id']='SPAN0004'
        with self.assertRaisesRegex(FlowError,'wrong source'):
            validate_production_plan(plan,data,PROFILE)

    def test_validation_rejects_first_frame_role_on_sheet_and_panel_overflow(self):
        data=storyboard(5,1000)
        original=build_production_plan(data,PROFILE)
        plan=copy.deepcopy(original)
        plan['boards'][0]['panels'][0]['frame_role']='first_frame'
        with self.assertRaisesRegex(FlowError,'cannot be first/last'):
            validate_production_plan(plan,data,PROFILE)
        plan=copy.deepcopy(original)
        plan['boards'][0]['panels']+=plan['boards'][1]['panels']
        with self.assertRaisesRegex(FlowError,'panel count'):
            validate_production_plan(plan,data,PROFILE)

    def test_validation_rejects_reordered_spans_or_missing_milliseconds(self):
        data=storyboard()
        original=build_production_plan(data,PROFILE,target_duration_ms=6000)
        plan=copy.deepcopy(original)
        plan['segments'][0]['source_spans'].reverse()
        with self.assertRaises(FlowError):
            validate_production_plan(plan,data,PROFILE)
        plan=copy.deepcopy(original)
        plan['segments'][0]['source_spans'][0]['source_end_ms']-=100
        with self.assertRaises(FlowError):
            validate_production_plan(plan,data,PROFILE)

    def test_accepts_shot_id_alias_but_not_conflicting_identity(self):
        data=storyboard(1,4000)
        data['items'][0]['shot_id']=data['items'][0].pop('id')
        self.assertEqual(build_production_plan(data,PROFILE)['segments'][0]['source_spans'][0]['shot_id'],'S001')
        data['items'][0]['id']='OTHER'
        with self.assertRaisesRegex(FlowError,'conflicting'):
            build_production_plan(data,PROFILE)

    def test_validation_rejects_lost_reference_and_wrong_continuity_binding(self):
        data=storyboard(1,4000)
        original=build_production_plan(data,PROFILE)
        plan=copy.deepcopy(original)
        plan['segments'][0]['reference_keys']=[]
        with self.assertRaisesRegex(FlowError,'reference_keys'):
            validate_production_plan(plan,data,PROFILE)
        plan=copy.deepcopy(original)
        plan['segments'][0]['continuity_in']['source_time_ms']=1000
        with self.assertRaisesRegex(FlowError,'continuity_in'):
            validate_production_plan(plan,data,PROFILE)

    def test_validation_rejects_board_list_reordered_across_segments(self):
        data=storyboard()
        plan=build_production_plan(data,PROFILE,target_duration_ms=6000)
        plan['boards'].reverse()
        with self.assertRaisesRegex(FlowError,'board list reorders'):
            validate_production_plan(plan,data,PROFILE)

    def test_board_reference_omission_and_asset_key_collision_are_rejected(self):
        data=storyboard(1,4000)
        original=build_production_plan(data,PROFILE)
        plan=copy.deepcopy(original)
        plan['boards'][0]['reference_keys']=[]
        with self.assertRaisesRegex(FlowError,'board source requirements'):
            validate_production_plan(plan,data,PROFILE)
        plan=copy.deepcopy(original)
        plan['boards'][0]['board_id']='CHAR001.work.front'
        with self.assertRaisesRegex(FlowError,'collides'):
            validate_production_plan(plan,data,PROFILE)


if __name__=='__main__':
    unittest.main()
