import os
import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from gpu_copy_timing import signature,revise
import gpu_jobs as gpu

class ProvenanceTests(unittest.TestCase):
    def test_proof_binds_text_voice_duration_portrait_and_photo_order(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'GPU_WORKER_TOKEN_FILE':tmp+'/token'}):
            Path(tmp+'/token').write_text('test-secret')
            ids=['a'*40,'b'*40];scenes=[{'narration':'Hello'},{'narration':'A room'}]
            original=signature(ids,ids[0],55,'en-male',scenes)
            for args in [(ids,ids[0],40,'en-male',scenes),(ids,ids[0],55,'en-female',scenes),(ids,ids[1],55,'en-male',scenes),(ids[::-1],ids[0],55,'en-male',scenes),(ids,ids[0],55,'en-male',[{'narration':'My edit'},scenes[1]])]:
                self.assertNotEqual(original,signature(*args))

    def test_manual_and_stale_lease_cannot_trigger_openai(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'GPU_JOB_DIR':tmp}),patch('gpu_copy_timing.urlopen') as api:
            with gpu.connect() as db:
                db.execute('INSERT INTO jobs VALUES(?,?,?,?,?)',('a'*40,'x','{"id":"'+('a'*40)+'","status":"rendering","options":{}}','lease',9999999999))
            with self.assertRaises(ValueError):revise({'id':'a'*40,'lease':'lease','attempt':1})
            with self.assertRaises(ValueError):revise({'id':'a'*40,'lease':'wrong','attempt':1})
            api.assert_not_called()

    def test_revision_cached_bounded_and_original_text_preserved(self):
        scenes=[{'photo_id':'b'*40,'narration':'Welcome to this home.'},{'photo_id':'c'*40,'narration':'The living room has large windows.'}]
        replacement=[dict(s,narration=s['narration']+' Enjoy the view.') for s in scenes]
        # Provider object order need not match the image order.
        keyed={s['photo_id']:s['narration'] for s in reversed(replacement)}
        result={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps({'scenes':keyed})}]}]}
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'GPU_JOB_DIR':tmp,'OPENAI_API_KEY':'test-key'}):
            job={'id':'a'*40,'status':'rendering','photo_ids':[s['photo_id'] for s in scenes],'options':{'auto_timing_revision':True,'duration_seconds':30,'voice':'en-male','scenes':scenes}}
            with gpu.connect() as db:db.execute('INSERT INTO jobs VALUES(?,?,?,?,?)',(job['id'],'x',json.dumps(job),'lease',9999999999))
            payload={'id':job['id'],'lease':'lease','attempt':1,'scene_seconds':[3,8]}
            with patch('gpu_copy_timing.urlopen',return_value=io.StringIO(json.dumps(result))) as api:
                first=revise(payload);self.assertEqual(revise(payload),first);api.assert_called_once()
            with gpu.connect() as db:stored=json.loads(db.execute('SELECT data FROM jobs').fetchone()[0])
            self.assertEqual(stored['options']['scenes'],scenes)
            self.assertEqual(stored['effective_scenes'],replacement)
            with self.assertRaises(ValueError):revise(dict(payload,attempt=3))

if __name__=='__main__':unittest.main()
