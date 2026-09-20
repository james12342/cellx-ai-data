import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import economy_videos as eco
import promo_videos as promo


class EconomyTests(unittest.TestCase):
    def payload(self):
        return dict(request_id='a'*40,photo_ids=['b'*40],options=dict(mode='economy',narration='看见日常的小美好。\n让这只杯子陪伴你的每一天。',voice='none',duration_seconds=15,aspect_ratio='9:16',brand='DEMO',cta='了解更多'))

    def test_invalid_inputs(self):
        for key,value in [('duration_seconds',True),('duration_seconds',float('nan')),('duration_seconds',61),('voice','bad'),('narration',''),('narration','x'*1201),('fit_narration','yes'),('clip_id','../../secret'),('brand','x'*46)]:
            payload=self.payload();payload['options'][key]=value
            with self.assertRaises(ValueError):eco.validate(payload)

    def test_chinese_script_matches_chinese_voice(self):
        payload=self.payload();payload['options']['voice']='en-female'
        self.assertEqual(eco.validate(payload)['voice'],'zh-female')
        self.assertEqual(eco.compatible_voice('en-male','第一行：吸引注意的开场'),'zh-male')
        self.assertEqual(eco.compatible_voice('en-female','Enjoy your morning coffee.'),'en-female')
        self.assertEqual(eco.compatible_voice('none','中文口播'),'none')

    def test_scene_mapping_and_ass_escape(self):
        opts=eco.validate(self.payload());text=eco.subtitles(opts,[5,10],720,1280)
        self.assertIn('0:00:05.00,0:00:15.00',text)
        self.assertIn('0:00:12.00,0:00:15.00,CTA',text)
        self.assertNotIn('{',eco.ass_text('{\\pos(1,2)}',40))
        self.assertEqual(eco.stamp(59.999),'0:01:00.00')

    def test_real_tts_timestamps_are_used(self):
        opts=eco.validate(self.payload())
        text=eco.subtitles(opts,[5,10],720,1280,[[(.5,1.25,'你好')],[(.1,2,'Hello')]])
        self.assertIn('0:00:00.50,0:00:01.25,Narration',text)
        self.assertIn('0:00:05.10,0:00:07.00,Narration',text)

    def test_dedupe_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=dict(id='a'*40,provider='economy',status='rendering')
            promo.write_status(root,job)
            with patch.object(eco,'render') as render:
                self.assertEqual(eco.start(root,self.payload())[1],200);render.assert_not_called()
            self.assertEqual(eco.poll(root,job)['status'],'failed')

    def test_missing_voice_and_missing_photo_release_worker(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'PHOTO_UPLOAD_DIR':tmp}):
            root=Path(tmp);payload=self.payload();payload['options']['voice']='zh-female'
            with patch.object(eco,'readiness',return_value={'renderer':True,'voice':False}):
                self.assertEqual(eco.start(root,payload)[1],503)
            payload['options']['voice']='none'
            with patch.object(eco,'readiness',return_value={'renderer':True,'voice':False}):
                self.assertEqual(eco.start(root,payload)[1],400)
            self.assertTrue(promo.WORKER.acquire(blocking=False));promo.WORKER.release()

    def test_srt_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'voice.srt';p.write_text('1\n00:00:00,100 --> 00:00:01,200\nHello\nworld\n',encoding='utf-8')
            self.assertEqual(eco.read_cues(p),[(.1,1.2,'Hello world')])

    def test_ai_narration_contract_and_cache(self):
        import product_briefs as briefs
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'PHOTO_UPLOAD_DIR':tmp,'OPENAI_API_KEY':'test-only'}):
            (Path(tmp)/('b'*40+'.bin')).write_bytes(b'fixture')
            response=MagicMock();response.__enter__.return_value=response
            response.read.return_value=json.dumps({'output':[{'content':[{'type':'output_text','text':json.dumps({'product_info':'A cup for your everyday moments.\nExplore the product.'})}]}]}).encode()
            payload={'photo_ids':['b'*40],'purpose':'narration','duration_seconds':30,'language':'en','product_info':'Blue cup'}
            briefs.CACHE.clear()
            with patch('runway_videos.photo_data',return_value=[{'uri':'data:image/png;base64,fixture'}]),patch.object(briefs,'urlopen',return_value=response) as api:
                result,status=briefs.generate(payload)
                self.assertEqual(status,200)
                sent=json.loads(api.call_args.args[0].data)
                self.assertIn('voiceover',sent['instructions']);self.assertIn('30 seconds',sent['instructions'])
                self.assertEqual(sent['text']['format']['type'],'json_object')
                self.assertIn('JSON',sent['input'][0]['content'][0]['text'])
                self.assertEqual(briefs.generate(payload)[0]['cached'],True);self.assertEqual(api.call_count,1)


if __name__=='__main__':unittest.main()
