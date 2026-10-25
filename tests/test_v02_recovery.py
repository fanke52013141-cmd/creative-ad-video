"""Recovery and import protocol checks using synthetic F01 inputs only."""
from pathlib import Path
import unittest

from PIL import Image

import test_v02_pipeline as pipeline_fixture
from video_flow import engine
from video_flow.contracts import FlowError
from video_flow.storage import read


class V02RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=pipeline_fixture.V02PipelineTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.run=self.fixture.run

    def test_asset_revision_reopens_only_consumers_and_reexports(self):
        fixture=self.fixture
        fixture.advance()
        before=read(self.run/'checkpoint.json')
        original_boards={key:value['sha256'] for key,value in before['stages']['board_media']['results'].items()}
        original_prompts={key:value['prompt'] for key,value in before['stages']['video_prompts']['results'].items()}
        old_board=next(p for p in fixture.packets if p['stage']=='board_media' and p['fanout']['item']=='SB001')
        old_path=self.run/old_board['fanout']['target_file']
        self.assertTrue(old_path.is_file())
        old_package=fixture.base/'before-revision'
        engine.package(self.run,format='external-production',out=old_package)
        engine.invalidate(self.run,'asset_media','Synthetic actor appearance change',item='CHAR001.default.front')
        state=read(self.run/'checkpoint.json')
        board_cells=state['stages']['board_media']['item_states']
        self.assertEqual({key for key,value in board_cells.items() if value['status']=='pending'},{'SB001','SB002'})
        self.assertEqual({key for key,value in board_cells.items() if value['status']=='done'},{'SB003','SB004'})
        prompt_cells=state['stages']['video_prompts']['item_states']
        self.assertEqual({key for key,value in prompt_cells.items() if value['status']=='pending'},
                         {'PROMPT-V001','PROMPT-V002'})
        self.assertEqual({key for key,value in prompt_cells.items() if value['status']=='done'},
                         {'PROMPT-V003','PROMPT-V004'})
        with self.assertRaisesRegex(FlowError,'stale'):
            engine.submit(self.run,old_board['task_id'])
        with self.assertRaisesRegex(FlowError,'accepted'):
            engine.package(self.run,format='external-production',out=fixture.base/'premature')
        fixture.advance()
        after=read(self.run/'checkpoint.json')
        for key in ('SB003','SB004'):
            self.assertEqual(after['stages']['board_media']['results'][key]['sha256'],original_boards[key])
        for key in ('PROMPT-V003','PROMPT-V004'):
            self.assertEqual(after['stages']['video_prompts']['results'][key]['prompt'],original_prompts[key])
        new_board=[p for p in fixture.packets if p['stage']=='board_media' and p['fanout']['item']=='SB001'][-1]
        self.assertNotEqual(old_board['fanout']['target_file'],new_board['fanout']['target_file'])
        self.assertTrue(old_path.is_file(),'Old accepted media is immutable history, not overwritten')
        result=engine.package(self.run,format='external-production',out=fixture.base/'after-revision')
        self.assertTrue(Path(result['package']).is_dir())
        self.assertEqual(engine.audit(self.run)['status'],'clean')
        from video_flow.delivery_validation import verify_package
        self.assertTrue(verify_package(old_package)['passed'],'Previously exported package remains a valid historical snapshot')

    def test_existing_image_import_still_requires_independent_review(self):
        fixture=self.fixture
        fixture.advance(stop_before='asset_media')
        source=fixture.base/'imported-character.png'
        Image.new('RGB',(1024,1536),(18,33,55)).save(source,'PNG')
        result=engine.import_media(self.run,'CHAR001.default.front',source)
        self.assertTrue(result)
        state=read(self.run/'checkpoint.json')
        cell=state['stages']['asset_media']['item_states']['CHAR001.default.front']
        self.assertEqual(cell['status'],'done')
        task=state['tasks'][cell['task_id']]
        self.assertTrue(task['agent_id'].startswith('import:'),task)
        self.assertNotEqual(state['stages']['asset_media_review']['status'],'accepted')
        self.assertNotIn('board_media',engine.status(self.run)['ready'])
        packet=read(self.run/task['path'])
        registered=state['stages']['asset_media']['results']['CHAR001.default.front']
        self.assertEqual(registered['source'],'imported')
        self.assertNotEqual((self.run/registered['file']).resolve(),source.resolve())
        self.assertEqual(packet['fanout']['item'],'CHAR001.default.front')

    def test_invalid_imported_image_is_rejected(self):
        fixture=self.fixture
        fixture.advance(stop_before='asset_media')
        source=fixture.base/'bad.png'
        source.write_bytes(b'not an image')
        with self.assertRaisesRegex(FlowError,'invalid image'):
            engine.import_media(self.run,'CHAR001.default.front',source)
        state=read(self.run/'checkpoint.json')
        self.assertNotIn('asset_media',state['artifacts'])
        self.assertNotEqual(state['stages']['asset_media_review']['status'],'accepted')


if __name__=='__main__':
    unittest.main()
