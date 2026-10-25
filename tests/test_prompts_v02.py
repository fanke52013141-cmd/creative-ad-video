"""Behavioral contracts for platform labels and explicitly deferred sound."""
from copy import deepcopy
import unittest

from video_flow.contracts import FlowError
from video_flow.prompts import validate_and_render


def prompt_fixture():
    references = [{'reference_key':'CHAR001.work.front', 'canonical_name':'CHAR001_小林_工作服_正面_r001',
                   'file':'media/character.png', 'sha256':'a'*64, 'media_revision':1,
                   'planned_slot':1, 'role':'人物外观与服装'}]
    timing = {'local_start_ms':0, 'local_end_ms':4000, 'span_id':'SPAN0001'}
    segment = {'video_id':'V001', 'mode':'reference', 'generation_duration_ms':4000,
               'timeline':[timing], 'continuity_in':{'state':'门旁站立'},
               'continuity_out':{'state':'回头看向门外'}}
    spec = {'item':'PROMPT-V001', 'segment':segment, 'references':references}
    candidate = {'schema_version':'0.2.0', 'type':'video_prompt', 'item':'PROMPT-V001',
                 'video_id':'V001', 'mode':'reference', 'duration_ms':4000,
                 'references':deepcopy(references),
                 'global_setting':'{{ref:CHAR001.work.front}}站在门旁。',
                 'timeline':[dict(timing, action='{{ref:CHAR001.work.front}}回头。',
                                  camera='固定机位', sound='门轴发出一声轻响')],
                 'audio':'一声门轴轻响，不加配乐。', 'constraints':'服装和空间保持连续。'}
    return candidate,spec


class PromptRenderingTests(unittest.TestCase):
    def test_declared_custom_platform_tag_used_everywhere(self):
        candidate,spec=prompt_fixture()
        output=validate_and_render(candidate,spec,{'supports_audio':True,'image_tag_template':'@ref{slot}'})
        self.assertIn('@ref1：CHAR001_小林_工作服_正面_r001',output['prompt'])
        self.assertIn('@ref1（CHAR001_小林_工作服_正面_r001）回头',output['prompt'])
        self.assertNotIn('@图片',output['prompt'])
        self.assertNotIn('{{ref:',output['prompt'])
        self.assertEqual(output['audio_delivery'],'native')

    def test_malformed_tag_templates_rejected(self):
        candidate,spec=prompt_fixture()
        for template in ('@ref{slot}{slot}','@ref{other}','@ref{slot!r}',
                         '@ref{slot:03d}','@ref{slot}{','@ref{{slot}}'):
            with self.subTest(template=template),self.assertRaisesRegex(FlowError,'template'):
                validate_and_render(candidate,spec,{'supports_audio':True,'image_tag_template':template})

    def test_unsupported_native_audio_deferred_and_preserved(self):
        candidate,spec=prompt_fixture()
        output=validate_and_render(candidate,spec,{'supports_audio':False})
        self.assertEqual(output['audio_delivery'],'postproduction')
        self.assertEqual(output['audio'],candidate['audio'])
        self.assertEqual(output['timeline'][0]['sound'],candidate['timeline'][0]['sound'])
        self.assertNotIn('声音：',output['prompt'])
        self.assertNotIn('门轴',output['prompt'])
        self.assertEqual(candidate['audio'],'一声门轴轻响，不加配乐。')

    def test_native_audio_included_when_capability_available(self):
        candidate,spec=prompt_fixture()
        output=validate_and_render(candidate,spec,{'supports_audio':True})
        self.assertEqual(output['audio_delivery'],'native')
        self.assertIn('声音：门轴发出一声轻响',output['prompt'])
        self.assertIn(candidate['audio'],output['prompt'])

    def test_unknown_reference_tokens_rejected(self):
        for field in ('global_setting','audio','constraints'):
            candidate,spec=prompt_fixture()
            candidate[field]='{{ref:UNKNOWN}}'
            with self.subTest(field=field),self.assertRaisesRegex(FlowError,'unknown reference'):
                validate_and_render(candidate,spec,{'supports_audio':True})

    def test_unknown_reference_in_deferred_audio_still_rejected(self):
        candidate,spec=prompt_fixture()
        candidate['audio']='{{ref:UNKNOWN}}的声音'
        with self.assertRaisesRegex(FlowError,'unknown reference'):
            validate_and_render(candidate,spec,{'supports_audio':False})

    def test_unknown_reference_in_deferred_timeline_sound_still_rejected(self):
        candidate,spec=prompt_fixture()
        candidate['timeline'][0]['sound']='{{ref:UNKNOWN}}发出响声'
        with self.assertRaisesRegex(FlowError,'unknown reference'):
            validate_and_render(candidate,spec,{'supports_audio':False})

    def test_raw_default_platform_labels_rejected(self):
        candidate,spec=prompt_fixture()
        for label in ('@图片2','@图3','@image4'):
            candidate['global_setting']=label+'站立'
            with self.subTest(label=label),self.assertRaisesRegex(FlowError,'reference tokens'):
                validate_and_render(candidate,spec,{'supports_audio':True})

    def test_raw_custom_platform_label_rejected(self):
        candidate,spec=prompt_fixture()
        candidate['global_setting']='@ref2站立'
        with self.assertRaisesRegex(FlowError,'reference tokens'):
            validate_and_render(candidate,spec,{'supports_audio':True,'image_tag_template':'@ref{slot}'})

    def test_unresolved_braces_rejected(self):
        candidate,spec=prompt_fixture()
        candidate['global_setting']='{{ref:CHAR001.work.front}'
        with self.assertRaisesRegex(FlowError,'unresolved'):
            validate_and_render(candidate,spec,{'supports_audio':True})

    def test_time_or_source_binding_tamper_rejected(self):
        for key,value in (('local_end_ms',4100),('local_start_ms',1),('span_id','SPAN_OTHER')):
            candidate,spec=prompt_fixture()
            candidate['timeline'][0][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(FlowError,'timeline'):
                validate_and_render(candidate,spec,{'supports_audio':True})

    def test_reference_name_hash_revision_and_slot_tamper_rejected(self):
        for key,value in (('canonical_name','OTHER'),('sha256','b'*64),
                          ('media_revision',2),('planned_slot',2),('file','elsewhere.png')):
            candidate,spec=prompt_fixture()
            candidate['references'][0][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(FlowError,'task bindings'):
                validate_and_render(candidate,spec,{'supports_audio':True})

    def test_rendered_text_must_match_structure_if_present(self):
        candidate,spec=prompt_fixture()
        candidate['prompt']='free form replacement'
        with self.assertRaisesRegex(FlowError,'rendered prompt differs'):
            validate_and_render(candidate,spec,{'supports_audio':True})


if __name__=='__main__':
    unittest.main()
