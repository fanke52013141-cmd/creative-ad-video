"""Synthetic F01 integration. These images/actors do not certify visual quality."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import yaml

from video_flow import engine
from video_flow.contracts import FlowError
from video_flow.production_plan import build_production_plan
from video_flow.production_runtime import mode_profile
from video_flow.storage import digest, read, write

ROOT = Path(__file__).resolve().parents[1]


def f01_artifacts():
    assets = []
    for index in (1, 2):
        shot_ids = [f'S{n:03d}' for n in range((index-1)*6+1, index*6+1)]
        for prefix, kind, label in [('CHAR', 'character', '人物'), ('SCENE', 'space', '场景'), ('PROP', 'prop', '物品')]:
            identity = f'{prefix}{index:03d}'
            assets.append({'id': identity, 'kind': kind, 'display_name': f'合成{label}{index}',
                           'description': f'Synthetic {kind}; not a real production asset',
                           'continuity_rules': 'Maintain the declared synthetic identity',
                           'invariant_features': ['Synthetic fixture'], 'shot_ids': shot_ids,
                           'states': [{'state_id': 'default', 'description': 'Default synthetic state', 'shot_ids': shot_ids}],
                           'media_requirements': [{'reference_key': identity+'.default.front', 'state_id': 'default',
                                                   'view': 'front', 'required': True, 'coverage_policy': 'independent'}]})
    story = []
    for index in (1, 2):
        story.append({'id': f'SC{index:03d}', 'scene_goal': 'Synthetic reveal', 'action': 'Observe a synthetic object',
                      'location': f'Location {index}', 'time': 'Night', 'characters': [f'CHAR{index:03d}'],
                      'dialogue': [], 'duration_ms': 12000})
    shots = []
    for order in range(1, 13):
        index = 1 if order <= 6 else 2
        bindings = [{'asset_id': f'{prefix}{index:03d}', 'state_id': 'default', 'purpose': 'Synthetic reference',
                     'start_state': 'Stable', 'end_state': 'Stable'} for prefix in ('CHAR','SCENE','PROP')]
        shots.append({'id':f'S{order:03d}', 'scene_id':f'SC{index:03d}', 'order':order, 'duration_ms':2000,
                      'shot_size':'Medium', 'camera_position':'South', 'primary_camera_motion':'Fixed',
                      'beat':f'Fixture beat {order}', 'action':f'Observe object in synthetic shot {order}',
                      'start_state':'Stable', 'end_state':'Stable', 'axis':'South-north',
                      'cut_motivation':'Next observation', 'lighting':'Stable window light',
                      'sound':'Silence', 'asset_bindings':bindings})
    return {
        'story': {'schema_version':'0.2.0', 'type':'story', 'items':story},
        'style': {'schema_version':'0.2.0', 'type':'style', 'items':[{'id':'LIGHT', 'axis':'lighting',
                  'rule':'Stable window light', 'story_reason':'Synthetic continuity fixture'}]},
        'storyboard': {'schema_version':'0.2.0', 'type':'storyboard', 'items':shots},
        'assets': {'schema_version':'0.2.0', 'type':'assets', 'items':assets},
        'edit_sound': {'schema_version':'0.2.0', 'type':'edit_sound', 'items':[{'id':f'ED{n:03d}',
                       'shot_id':f'S{n:03d}', 'picture_cut':'At end', 'sound':'Silence',
                       'motivation':'Synthetic fixture'} for n in range(1,13)]}}


class V02PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.prepare(Path(self.temp.name))

    def prepare(self, base):
        self.base = Path(base)
        self.root = self.base/'source'
        (self.root/'config').mkdir(parents=True)
        for name in ('workflow.yaml','routes.yaml'):
            shutil.copyfile(ROOT/'config'/name, self.root/'config'/name)
        names = {'script-ad','script-shortfilm'}
        for row in engine.load_yaml(self.root/'config/workflow.yaml')['stages']:
            names.add(row['skill'])
            for spec in (row, row.get('production',{})):
                names.update(spec.get('fanout',{}).get('skill_by_kind',{}).values())
        names.discard('$writer')
        for name in names:
            path=self.root/'.agents/skills'/name/'SKILL.md'
            path.parent.mkdir(parents=True)
            path.write_text('Synthetic contract test skill: '+name,encoding='utf-8')
        self.config=self.base/'profiles'
        self.config.mkdir()
        production={'schema_version':'0.2.0','profile_id':'F01','media_mode':'mock','selected_mode':'reference',
                    'target_segment_duration_ms':6000, 'platform_profile':'platform.yaml','provider_profile':'provider.yaml',
                    'board_max_panels':4,'max_concurrent_media':1,'repair_limit':2,
                    'delivery':{'text_encoding':'utf-8-sig','directory_name':'{title}_制作包_r{revision:03d}'},
                    'budget':{'paid_generation_authorized':False,'max_total_cost':None,'currency':'USD'}}
        platform={'schema_version':'0.2.0','profile_id':'F01','status':'test_only',
                  'source':'Synthetic finite capability; not a real platform specification','verified_at':None,
                  'modes':{'reference':{'min_duration_ms':4000,'max_duration_ms':10000,'max_images':8,
                                       'supports_multi_shot':True,'supports_audio':False}}}
        provider={'schema_version':'0.2.0','profile_id':'F01','status':'test_only','test_only':True,
                  'supports_reference_images':True,'formats':['png'],'credential_env':None}
        for name,value in [('production',production),('platform',platform),('provider',provider)]:
            (self.config/(name+'.yaml')).write_text(yaml.safe_dump(value,allow_unicode=True),encoding='utf-8')
        self.run=self.base/'run'
        self.brief=read(ROOT/'examples/v02/brief.json')
        engine.initialize(self.run,self.brief,'automatic',root=self.root,media=True,
                          production_config=self.config/'production.yaml')
        self.fixtures=f01_artifacts()
        self.packets=[]

    def dispatch(self,stage,item=None):
        packet=engine.dispatch(self.run,stage,item)
        prefix='reviewer' if packet['review_target'] else 'author'
        engine.bind(self.run,packet['task_id'],prefix+'-'+packet['task_id'])
        self.packets.append(packet)
        return packet

    def put(self,packet,candidate):
        value=deepcopy(candidate)
        value.update(task_id=packet['task_id'],schema_version='0.2.0')
        base=Path(packet['output_root'])
        write(base/'candidate.json',value)
        state=read(self.run/'checkpoint.json')
        write(base/'receipt.json',{'task_id':packet['task_id'],'agent_id':state['tasks'][packet['task_id']]['agent_id'],
                                  'skill_sha256':packet['skill_sha256'],'input_hashes':packet['input_hashes'],
                                  'output_sha256':digest(base/'candidate.json')})

    def review_candidate(self,packet):
        target=packet['review_target']
        return {'type':'review','target_sha256':packet['input_hashes'][target],
                'coverage':[x.get('id') or x.get('item') for x in packet['inputs'][target]['items']],
                'verdict':'pass','issues':[],
                'criteria':[{'name':name,'score':3,'evidence':'Synthetic protocol fixture; no visual or creative certification'}
                            for name in packet['review_criteria']]}

    def plan_candidate(self,packet):
        storyboard=deepcopy(packet['inputs']['storyboard'])
        assets={a['id']:a for a in packet['inputs']['assets']['items']}
        for shot in storyboard['items']:
            shot['reference_keys']=[m['reference_key'] for binding in shot['asset_bindings']
                                    for m in assets[binding['asset_id']]['media_requirements']
                                    if m['state_id']==binding['state_id'] and m['required']]
        config=packet['production']
        plan=build_production_plan(storyboard,mode_profile(config),
                                  target_duration_ms=config['production']['target_segment_duration_ms'],
                                  max_panels=config['production']['board_max_panels'])
        plan['items']=[dict(s,id=s['video_id']) for s in plan['segments']]
        return plan

    def media_candidate(self,packet,bad=False):
        row=packet['fanout']
        path=self.run/row['target_file']
        path.parent.mkdir(parents=True,exist_ok=True)
        if bad:
            path.write_bytes(b'not an image')
        else:
            width,height=map(int,row['size'].split('x'))
            Image.new('RGB',(width,height),(23,40,60)).save(path,'PNG')
        return {'type':'media_item','item':row['item'],'file':row['target_file'],'sha256':digest(path),
                'prompt':'Synthetic mechanical test image; no visual fidelity claim',
                'model':'fixture','quality':'synthetic','source':'mock'}

    def prompt_candidate(self,packet):
        spec=packet['fanout']['spec']
        segment=spec['segment']
        refs=packet['fanout']['references']
        token='{{ref:'+refs[0]['reference_key']+'}}'
        return {'type':'video_prompt','item':spec['item'],'video_id':segment['video_id'],'mode':segment['mode'],
                'duration_ms':segment['generation_duration_ms'],'references':deepcopy(refs),
                'global_setting':'Synthetic scene using '+token,
                'timeline':[dict(row,action='Observe '+token,camera='Fixed',sound='Silence') for row in segment['timeline']],
                'audio':'Silence','constraints':'Maintain declared identities'}

    def advance(self,stop_before=None):
        for _ in range(100):
            snapshot=engine.status(self.run)
            ready=snapshot['ready']
            if not ready:
                self.assertTrue(all(s['status']=='accepted' for s in snapshot['stages'].values()),snapshot)
                return
            stage=ready[0]
            if stage==stop_before:
                return
            workflow=read(self.run/'standard/workflow.json')
            row=next(x for x in workflow['stages'] if x['id']==stage)
            if row.get('fanout'):
                state=read(self.run/'checkpoint.json')
                queue=engine.fanout_queue(self.run,state,row)
                entry=state['stages'][stage]
                item=next(x['item'] for x in queue if entry.get('item_states',{}).get(x['item'],{}).get('status','pending')=='pending')
                packet=self.dispatch(stage,item)
                candidate=self.prompt_candidate(packet) if packet['artifact_type']=='video_prompt' else self.media_candidate(packet)
            else:
                packet=self.dispatch(stage)
                if row.get('reviews'):
                    candidate=self.review_candidate(packet)
                elif stage=='production_plan':
                    candidate=self.plan_candidate(packet)
                else:
                    candidate=self.fixtures[stage]
            self.put(packet,candidate)
            engine.submit(self.run,packet['task_id'])
        self.fail('synthetic pipeline did not terminate within bounded dispatch count')

    def test_f01_complete_package_and_slices(self):
        # An accidental online generation attempt must fail this offline fixture.
        with patch('urllib.request.urlopen', side_effect=AssertionError('Offline fixture must not make network calls')), \
             patch('socket.create_connection', side_effect=AssertionError('Offline fixture must not open a network connection')):
            self.advance()
        state=read(self.run/'checkpoint.json')
        self.assertEqual(state['version'],'0.2.0')
        self.assertEqual(len(state['stages']),18)
        media=engine.artifact(self.run,state,'asset_media')['items']
        self.assertEqual({r['kind'] for r in media},{'character','space','prop'})
        self.assertEqual(len(media),6)
        boards=[p for p in self.packets if p['stage']=='board_media']
        self.assertEqual(len(boards),4)
        for packet in boards:
            self.assertEqual(len(packet['inputs']['storyboard']['items']),3)
            self.assertEqual(len(packet['fanout']['references']),3)
            for ref in packet['fanout']['references']:
                self.assertEqual(digest(self.run/ref['file']),ref['sha256'])
        prompts=[p for p in self.packets if p['stage']=='video_prompts']
        self.assertEqual(len(prompts),4)
        for packet in prompts:
            self.assertEqual(len(packet['inputs']['storyboard']['items']),3)
            self.assertEqual(len(packet['inputs']['board_media']['items']),1)
            self.assertEqual(len(packet['fanout']['references']),4)
            self.assertEqual(packet['fanout']['spec']['segment']['generation_duration_ms'],6000)
        output=self.base/'delivery'
        result=engine.package(self.run,format='external-production',out=output)
        self.assertTrue(result)
        self.assertEqual(len(list(output.rglob('*.png'))),10)
        self.assertEqual(len(list(output.rglob('*_视频提示词.txt'))),4)
        self.assertEqual(len(list(output.rglob('*_参考图映射.txt'))),4)
        for name in ('剧本.txt','详细分镜.txt','交付清单.txt'):
            self.assertTrue((output/name).read_text(encoding='utf-8-sig').strip())
        from video_flow.delivery_validation import verify_package
        relocated=self.base/'relocated'
        shutil.copytree(output,relocated)
        report=verify_package(relocated)
        self.assertTrue(report['passed'],report)
        manifest=read(output/'_校验/manifest.json')
        self.assertEqual(manifest['status'],'synthetic_package_ready')
        self.assertTrue(manifest['synthetic'])
        self.assertEqual(manifest['external_result_status'],'unverified')
        cli_environment=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
        for args in (['verify-package',str(relocated)],['audit',str(self.run)]):
            process=subprocess.run([sys.executable,'-m','video_flow',*args],cwd=ROOT,
                                   capture_output=True,text=True,encoding='utf-8',env=cli_environment)
            self.assertEqual(process.returncode,0,process.stderr+process.stdout)
            result=json.loads(process.stdout)
            if args[0]=='audit':
                self.assertEqual(result['status'],'clean',result)
            else:
                self.assertTrue(result['passed'],result)
        # CLI must independently reject changed bytes instead of trusting its saved report.
        image=next(relocated.rglob('*.png'))
        image.write_bytes(b'changed after validation')
        process=subprocess.run([sys.executable,'-m','video_flow','verify-package',str(relocated)],cwd=ROOT,
                               capture_output=True,text=True,encoding='utf-8',env=cli_environment)
        self.assertEqual(process.returncode,1,process.stderr+process.stdout)

    def test_board_waits_for_asset_review(self):
        self.advance(stop_before='asset_media')
        with self.assertRaisesRegex(FlowError,'not ready'):
            engine.dispatch(self.run,'board_media','SB001')
        self.assertNotIn('board_media',engine.status(self.run)['ready'])

    def test_config_tamper_blocks_progress(self):
        path=self.run/'standard/production.json'
        value=read(path)
        value['production']['board_max_panels']=3
        write(path,value)
        with self.assertRaisesRegex(FlowError,'standard changed'):
            engine.dispatch(self.run,'story')

    def test_bad_image_rejected_without_submission(self):
        self.advance(stop_before='asset_media')
        packet=self.dispatch('asset_media','CHAR001.default.front')
        self.put(packet,self.media_candidate(packet,bad=True))
        with self.assertRaisesRegex(FlowError,'invalid image'):
            engine.submit(self.run,packet['task_id'])
        state=read(self.run/'checkpoint.json')
        self.assertNotIn('asset_media',state['artifacts'])

    def test_prompt_unknown_reference_rejected(self):
        self.advance(stop_before='video_prompts')
        packet=self.dispatch('video_prompts','PROMPT-V001')
        candidate=self.prompt_candidate(packet)
        candidate['global_setting']='Unknown {{ref:NOT_REGISTERED}}'
        self.put(packet,candidate)
        with self.assertRaisesRegex(FlowError,'unknown reference'):
            engine.submit(self.run,packet['task_id'])


def generate_f01(destination):
    """Persist an explicitly synthetic mechanical sample outside the repository."""
    destination=Path(destination).resolve()
    if destination.exists():
        raise ValueError('F01 destination must not already exist')
    destination.mkdir(parents=True)
    runner=V02PipelineTests('test_f01_complete_package_and_slices')
    runner.prepare(destination)
    runner.advance()
    result=engine.package(runner.run,format='external-production',out=destination/'delivery')
    state=read(runner.run/'checkpoint.json')
    evidence={'fixture':'F01','synthetic':True,'visual_quality_verified':False,
              'external_video_generated':False,'run':str(runner.run),'package':result['package'],
              'task_count':len(state['tasks']),'stage_count':len(state['stages']),
              'image_count':len(list((destination/'delivery').rglob('*.png'))),
              'video_prompt_count':len(list((destination/'delivery').rglob('*_视频提示词.txt'))),
              'audit':engine.audit(runner.run)}
    write(destination/'evidence.json',evidence)
    return evidence


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--write-f01':
        print(json.dumps(generate_f01(sys.argv[2]),ensure_ascii=False,indent=2))
    else:
        unittest.main()
