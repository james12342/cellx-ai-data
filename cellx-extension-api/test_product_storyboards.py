import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import product_briefs
import product_storyboards as storyboard


class StoryboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'PHOTO_UPLOAD_DIR':str(self.folder),'OPENAI_API_KEY':'test-only-key','PRODUCT_BRIEF_MODEL':'gpt-4o-mini'})
        self.env.start();product_briefs.CACHE.clear()
        self.ids=[c*40 for c in 'abcd']
        for photo_id in self.ids:
            Image.new('RGB',(1200,800),(100,20,30)).save(self.folder/(photo_id+'.bin'),format='JPEG')
        self.payload={'photo_ids':self.ids,'language':'zh-CN','duration_seconds':30,'purpose':'storyboard'}
        self.speech=patch.object(storyboard,'synthesize',return_value=[7.5]*4);self.speech.start()
        self.correction=patch.object(storyboard,'correct',side_effect=lambda work,ds,target:([target*d/sum(ds) for d in ds],sum(ds)/target));self.correction.start()

    def tearDown(self): self.speech.stop();self.correction.stop();self.env.stop();self.tmp.cleanup()

    def response(self,ids=None):
        parsed={'product_info':'Visible product. Details need confirmation.','scenes':[{'photo_id':i,'visual_description':'Visible scene','narration':'Short voiceover'} for i in (ids or self.ids)]}
        return io.BytesIO(json.dumps({'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(parsed)}]}],'usage':{'total_tokens':20}}).encode())

    def test_batch_order_schema_resize_and_cache(self):
        with patch.object(storyboard,'urlopen',return_value=self.response()) as call:
            result,status=product_briefs.generate(self.payload)
            self.assertEqual(status,200);self.assertEqual(result['photo_ids'],self.ids)
            body=json.loads(call.call_args.args[0].data)
            self.assertEqual(body['text']['format']['type'],'json_schema')
            self.assertTrue(body['text']['format']['strict'])
            content=body['input'][0]['content']
            self.assertEqual(len([x for x in content if x['type']=='input_image']),4)
            for index,photo_id in enumerate(self.ids):self.assertIn(photo_id,content[1+index*2]['text'])
            again,status=product_briefs.generate(self.payload)
            self.assertTrue(again['cached']);self.assertEqual(call.call_count,1)

    def test_wrong_output_order_rejected(self):
        with patch.object(storyboard,'urlopen',return_value=self.response(list(reversed(self.ids)))):
            result,status=storyboard.generate(self.payload)
            self.assertEqual(status,400);self.assertIn('order',result['message'])

    def test_deleted_image_invalidates_cache(self):
        with patch.object(storyboard,'urlopen',return_value=self.response()) as call:
            self.assertEqual(storyboard.generate(self.payload)[1],200)
            (self.folder/(self.ids[0]+'.bin')).unlink()
            self.assertEqual(storyboard.generate(self.payload)[1],400)
            self.assertEqual(call.call_count,1)

    def test_timeout_has_no_automatic_retry(self):
        with patch.object(storyboard,'urlopen',side_effect=TimeoutError) as call:
            result,status=storyboard.generate(self.payload)
            self.assertEqual(status,502);self.assertEqual(call.call_count,1)
            self.assertIn('Retry',result['message'])

    def test_validation_before_api(self):
        for ids in [[],self.ids*3,['../bad']]:
            with patch.object(storyboard,'urlopen') as call:
                self.assertEqual(storyboard.generate({**self.payload,'photo_ids':ids})[1],400)
                call.assert_not_called()

    def test_40_55_seconds_voice_notes_and_cache(self):
        for seconds,voice in [(40,'zh-female'),(55,'zh-male')]:
            with patch.object(storyboard,'synthesize',return_value=[seconds/4]*4),patch.object(storyboard,'urlopen',return_value=self.response()) as call:
                result,status=storyboard.generate({**self.payload,'duration_seconds':seconds,'voice':voice,'product_info':'Known product facts'})
                self.assertEqual(status,200);self.assertTrue(result['timing']['matched'])
                self.assertEqual(result['timing']['measured_seconds'],seconds)
                self.assertAlmostEqual(sum(s['duration_seconds'] for s in result['scenes']),seconds)
                body=json.loads(call.call_args.args[0].data)
                self.assertIn(f'{seconds} seconds using {voice}',body['instructions'])
                self.assertIn('Known product facts',body['input'][0]['content'][0]['text'])
        self.assertEqual(len(product_briefs.CACHE),2)

    def test_one_revision_from_measured_short_audio(self):
        with patch.object(storyboard,'synthesize',side_effect=[[2.5]*4,[10]*4]),patch.object(storyboard,'urlopen',side_effect=[self.response(),self.response()]) as call:
            result,status=storyboard.generate({**self.payload,'duration_seconds':40})
            self.assertEqual(status,200);self.assertEqual(call.call_count,2)
            self.assertTrue(result['timing']['matched']);self.assertEqual(result['timing']['revisions'],1)
            self.assertEqual(result['usage']['total_tokens'],40)
            self.assertIn('actually synthesized to 10.0s',json.loads(call.call_args.args[0].data)['instructions'])

    def test_persistent_mismatch_is_not_claimed_as_target(self):
        with patch.object(storyboard,'synthesize',return_value=[2.5]*4),patch.object(storyboard,'urlopen',side_effect=[self.response(),self.response()]) as call:
            result,status=storyboard.generate({**self.payload,'duration_seconds':55})
            self.assertEqual(status,200);self.assertEqual(call.call_count,2)
            self.assertFalse(result['timing']['matched']);self.assertEqual(result['timing']['measured_seconds'],10)
            self.assertTrue(result['timing_warning']);self.assertEqual(len(product_briefs.CACHE),0)

    def test_portrait_role_budget_defers_all_speech_compute_to_gpu(self):
        with patch.object(storyboard,'synthesize') as speech,patch.object(storyboard,'urlopen',return_value=self.response()) as api:
            result,status=storyboard.generate({**self.payload,'portrait_photo_id':self.ids[0],'duration_seconds':55})
            self.assertEqual(status,200);speech.assert_not_called()
            self.assertEqual(result['timing']['verification_location'],'gpu-worker')
            self.assertFalse(result['timing']['verified'])
            schema=json.loads(api.call_args.args[0].data)['text']['format']['schema']
            variants=schema['properties']['scenes']['items']['anyOf']
            self.assertEqual(len(variants),4)
            self.assertEqual(variants[0]['properties']['photo_id']['enum'],[self.ids[0]])
            self.assertLess(variants[0]['properties']['narration']['minLength'],variants[1]['properties']['narration']['minLength'])
            self.assertLessEqual(variants[0]['properties']['narration']['maxLength'],100)

    def test_long_mixed_boundaries_leave_economy_at_60(self):
        for seconds in [60,61,75,120,299,300,301]:
            with patch.object(storyboard,'synthesize') as speech,patch.object(storyboard,'urlopen',return_value=self.response()) as api:
                result,status=storyboard.generate({**self.payload,'portrait_photo_id':self.ids[0],'duration_seconds':seconds})
                self.assertEqual(status,200 if seconds<=300 else 400);speech.assert_not_called()
                if 60<seconds<=300:
                    body=json.loads(api.call_args.args[0].data)
                    self.assertGreater(body['max_output_tokens'],4000)
                    self.assertIn('evidence_sufficient',body['text']['format']['schema']['required'])
            if seconds>60:self.assertEqual(storyboard.generate({**self.payload,'duration_seconds':seconds})[1],400)

    def test_insufficient_evidence_keeps_user_text_and_explains(self):
        result={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps({'evidence_sufficient':False,'product_info':'Need more photos','scenes':[]})}]}]}
        with patch.object(storyboard,'urlopen',return_value=io.BytesIO(json.dumps(result).encode())):
            answer,status=storyboard.generate({**self.payload,'portrait_photo_id':self.ids[0],'duration_seconds':300})
            self.assertEqual(status,400);self.assertIn('Not enough evidence',answer['message'])


if __name__=='__main__':unittest.main()
