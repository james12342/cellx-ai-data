import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import promo_videos as v


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'PROMO_VIDEO_DIR':self.temp.name,'PHOTO_UPLOAD_DIR':self.temp.name})
        self.env.start()
    def tearDown(self):
        self.env.stop();self.temp.cleanup()
    def test_options(self):
        self.assertEqual(v.options_from({})['aspect_ratio'],'9:16')
        for options in [{'duration_seconds':float('nan')},{'duration_seconds':61},{'duration_seconds':0},{'aspect_ratio':'evil'},{'music_preset':'http://bad'},[]]:
            if options==[]:continue
            with self.assertRaises(ValueError):v.options_from(options)
    def test_invalid_and_traversal(self):
        for ids in [[],['../secret'],['a'*40]*11]:
            self.assertEqual(v.video_request('POST','/promo-videos',{'photo_ids':ids})[1],400)
        self.assertEqual(v.video_request('GET','/promo-videos/../../secret',{})[1],404)
    def test_missing_releases_worker(self):
        with patch('promo_videos.shutil.which',return_value='/usr/bin/tool'):
            for _ in range(2):self.assertEqual(v.video_request('POST','/promo-videos',{'photo_ids':['a'*40]})[1],400)
    def test_busy(self):
        v.WORKER.acquire()
        try:
            with patch('promo_videos.shutil.which',return_value='/usr/bin/tool'):
                self.assertEqual(v.video_request('POST','/promo-videos',{'photo_ids':['a'*40]})[1],409)
        finally:v.WORKER.release()
    def test_status_download_delete(self):
        root=Path(self.temp.name);job={'ok':True,'id':'a'*40,'status':'completed'}
        v.write_status(root,job);(root/('a'*40+'.mp4')).write_bytes(b'mp4fixture')
        self.assertEqual(v.video_request('GET','/promo-videos/'+'a'*40,{})[0]['status'],'completed')
        self.assertIsInstance(v.video_request('GET','/promo-videos/'+'a'*40+'/file',{})[0],Path)
        self.assertEqual(v.video_request('DELETE','/promo-videos/'+'a'*40,{})[1],200)
        self.assertEqual(v.video_request('GET','/promo-videos/'+'a'*40,{})[1],404)

if __name__=='__main__':unittest.main()
