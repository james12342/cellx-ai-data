"""Exercise the real HTTP handler without loading server startup integrations."""
import ast
import io
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch
from urllib.parse import urlparse


class VideoRequestSizeTests(unittest.TestCase):
    def request(self, payload, size=None):
        tree = ast.parse(Path(__file__).with_name('server.py').read_text(encoding='utf-8'))
        handler = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Handler')
        method = next(n for n in handler.body if isinstance(n, ast.FunctionDef) and n.name == 'serve_promo_video')
        ns = dict(json=json, urlparse=urlparse, normalize_api_path=lambda p:p,
                  ai_voice_auth=lambda s:(True,None,200))
        exec(compile(ast.Module(body=[method],type_ignores=[]),'server.py','exec'),ns)
        data=json.dumps(payload).encode()
        if size is not None:
            data += b' '*(size-len(data))
        fake=types.SimpleNamespace(headers={'Content-Length':str(len(data))},command='POST',path='/promo-videos',
            rfile=io.BytesIO(data),wfile=io.BytesIO(),_headers=lambda *a:None,
            send_header=lambda *a:None,end_headers=lambda:None)
        fake.send_response=lambda value:setattr(fake,'status',value)
        route=types.SimpleNamespace(video_request=lambda *a:({'ok':True},200))
        with patch.dict('sys.modules',{'promo_videos':route}):
            ns['serve_promo_video'](fake)
        return fake.status

    def test_long_chinese_hybrid_and_transport_ceiling(self):
        body={'options':{'mode':'portrait_storyboard','narration':'房'*10000,
                         'storyboard_scenes':[{'narration':'房'*10000}]}}
        self.assertEqual(self.request(body),200)
        self.assertEqual(self.request(body,512*1024),200)
        self.assertEqual(self.request(body,512*1024+1),400)

    def test_existing_mode_limits_and_malformed_shapes(self):
        for mode in ['economy','portrait','runway']:
            body={'options':{'mode':mode}}
            self.assertEqual(self.request(body,32768),200)
            self.assertEqual(self.request(body,32769),400)
        self.assertEqual(self.request([]),400)
        self.assertEqual(self.request({'options':[]},32769),400)


if __name__=='__main__':unittest.main()
