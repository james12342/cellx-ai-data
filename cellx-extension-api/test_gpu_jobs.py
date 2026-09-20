import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import gpu_jobs as gpu


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {'GPU_JOB_DIR':str(self.root/'jobs'), 'PHOTO_UPLOAD_DIR':str(self.root/'photos'), 'GPU_WORKER_TOKEN_FILE':str(self.root/'token')})
        self.env.start()
        (self.root/'photos').mkdir()
        (self.root/'photos'/('b'*40+'.bin')).write_bytes(b'\xff\xd8\xff' + b'x'*100)
        (self.root/'token').write_text('dedicated-secret')
        self.payload = {'request_id':'a'*40, 'photo_ids':['b'*40], 'options':{'narration':'Hello there', 'voice':'en-male', 'aspect_ratio':'9:16'}}

    def tearDown(self):
        self.env.stop(); self.tmp.cleanup()

    def test_idempotency_and_conflict(self):
        self.assertEqual(gpu.start(self.payload)[1],202)
        self.assertEqual(gpu.start(self.payload)[1],200)
        self.payload['options']['narration']='Changed'
        self.assertEqual(gpu.start(self.payload)[1],409)

    def test_single_claim_expiry_and_stale_worker(self):
        gpu.start(self.payload)
        claim=gpu.worker_action('claim',{})
        self.assertEqual(claim['job']['status'],'rendering')
        self.assertIsNone(gpu.worker_action('claim',{})['job'])
        with gpu.connect() as db: db.execute('UPDATE jobs SET deadline=?',(time.time()-1,))
        self.assertEqual(gpu.video_request('GET','a'*40)[0]['status'],'queued')
        new=gpu.worker_action('claim',{})
        self.assertNotEqual(new['lease'],claim['lease'])
        with self.assertRaises(ValueError): gpu.worker_action('heartbeat',{'id':'a'*40,'lease':claim['lease']})

    def test_failure_and_retry_limit(self):
        gpu.start(self.payload)
        for attempt in range(3):
            claim=gpu.worker_action('claim',{})
            gpu.worker_action('fail',{'id':'a'*40,'lease':claim['lease'],'retryable':True})
        self.assertEqual(gpu.video_request('GET','a'*40)[0]['status'],'failed')
        self.assertEqual(gpu.video_request('DELETE','a'*40)[1],200)

    def test_auth_and_validation(self):
        self.assertFalse(gpu.authorized({}))
        self.assertFalse(gpu.authorized({'Authorization':'Bearer wrong'}))
        self.assertTrue(gpu.authorized({'Authorization':'Bearer dedicated-secret'}))
        self.payload['photo_ids']=['../outside']
        self.assertEqual(gpu.start(self.payload)[1],400)

    def test_completed_upload_retries_do_not_requeue(self):
        gpu.start(self.payload)
        claim=gpu.worker_action('claim',{})
        with gpu.connect() as db:
            job=claim['job'];job.update(status='completed')
            gpu.save(db,job);db.execute('UPDATE jobs SET deadline=0')
        gpu.worker_action('fail',{'id':job['id'],'lease':claim['lease'],'retryable':True})
        self.assertEqual(gpu.video_request('GET',job['id'])[0]['status'],'completed')

    def test_multi_photo_snapshot_role_order_and_worker_version(self):
        other='c'*40
        (self.root/'photos'/(other+'.bin')).write_bytes(b'\xff\xd8\xff'+b'y'*100)
        self.payload['photo_ids']=[other,'b'*40]
        self.payload['options'].update(mode='portrait_storyboard',portrait_photo_id='b'*40,duration_seconds=20,narration='Welcome\nSee the house',storyboard_scenes=[{'photo_id':'b'*40,'narration':'Welcome'},{'photo_id':other,'narration':'See the house'}])
        job,status=gpu.start(self.payload)
        self.assertEqual(status,202);self.assertEqual(job['photo_ids'],['b'*40,other]);self.assertEqual(job['photo_count'],2)
        self.assertEqual(gpu.photo_path(job['id'],1).read_bytes(),b'\xff\xd8\xff'+b'y'*100)
        self.assertIsNone(gpu.worker_action('claim',{})['job'],'old worker must not consume new jobs')
        claimed=gpu.worker_action('claim',{'capabilities':['portrait_storyboard_v1']})
        self.assertEqual(claimed['job']['id'],job['id']);self.assertTrue(gpu.readiness()['storyboard_ready'])
        with self.assertRaises(ValueError):gpu.photo_path(job['id'],10)
        self.payload['options']['storyboard_scenes'].reverse()
        self.assertEqual(gpu.start(self.payload)[1],400)

    def test_long_duration_boundaries_and_long_manual_script(self):
        import hashlib
        other='c'*40;(self.root/'photos'/(other+'.bin')).write_bytes(b'\xff\xd8\xff'+b'y'*100)
        lines=['Welcome','Visible details. '*260]
        for seconds in [60,61,75,120,299,300,301]:
            payload={'request_id':hashlib.sha1(str(seconds).encode()).hexdigest(),'photo_ids':['b'*40,other],
                     'options':{'mode':'portrait_storyboard','portrait_photo_id':'b'*40,'duration_seconds':seconds,'narration':'\n'.join(lines),'storyboard_scenes':[{'photo_id':i,'narration':s} for i,s in zip(['b'*40,other],lines)]}}
            job,status=gpu.start(payload)
            self.assertEqual(status,202 if seconds<=300 else 400)
            if status==202:self.assertEqual(job['options']['scenes'][1]['narration'],lines[1].strip());self.assertFalse(job['options'].get('auto_timing_revision'))
        self.payload['options']['narration']='x'*101
        self.assertEqual(gpu.start(self.payload)[1],400,'pure portrait still has short-script protection')

    def test_old_worker_does_not_claim_300_second_job(self):
        other='c'*40;(self.root/'photos'/(other+'.bin')).write_bytes(b'\xff\xd8\xff'+b'y'*100)
        self.payload.update(photo_ids=['b'*40,other]);self.payload['options'].update(mode='portrait_storyboard',portrait_photo_id='b'*40,duration_seconds=300,storyboard_scenes=[{'photo_id':'b'*40,'narration':'Welcome'},{'photo_id':other,'narration':'House'}])
        self.assertEqual(gpu.start(self.payload)[1],202)
        self.assertIsNone(gpu.worker_action('claim',{'capabilities':['portrait_storyboard_v1']})['job'])
        self.assertIsNotNone(gpu.worker_action('claim',{'capabilities':['portrait_storyboard_v1','portrait_storyboard_300_v2']})['job'])


if __name__ == '__main__': unittest.main()
