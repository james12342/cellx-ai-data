"""Validate product-brief behavior on AWS with a mocked provider, no API charge."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, '/opt/cellx-extension-api')
import product_briefs

pid=subprocess.check_output(['systemctl','show','cellx-extension-api','-p','MainPID','--value'],text=True).strip()
env=dict(p.decode().split('=',1) for p in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if b'=' in p)
print('OpenAI key configured:',bool(env.get('OPENAI_API_KEY')))
with tempfile.TemporaryDirectory(prefix='brief-check-') as temporary:
    root=Path(temporary)
    file_id='a'*40
    (root/(file_id+'.bin')).write_bytes(b'\x89PNG\r\n\x1a\nfixture')
    (root/(file_id+'.json')).write_text(json.dumps({'mime_type':'image/png'}))
    payload={'photo_ids':[file_id],'product_info':'User-confirmed cup','language':'zh-CN'}
    response={'output':[{'content':[{'type':'output_text','text':json.dumps({'product_info':'Product draft; capacity requires confirmation.'})}]}],'usage':{'input_tokens':100,'output_tokens':40,'total_tokens':140}}
    with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','PHOTO_UPLOAD_DIR':temporary}):
        with patch.object(product_briefs,'urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as call:
            result,code=product_briefs.generate(payload)
            assert code==200 and result['usage']['total_tokens']==140
            assert call.call_count==1
            request=json.loads(call.call_args.args[0].data)
            assert request['store'] is False and request['max_output_tokens']==1000
            assert request['input'][0]['content'][1]['type']=='input_image'
            assert 'test-only' not in json.dumps(result)
        with patch.object(product_briefs,'urlopen') as call:
            cached,code=product_briefs.generate(payload)
            assert code==200 and cached['cached'] and cached['usage']['total_tokens']==0
            assert call.call_count==0
        product_briefs.CACHE.clear()
        with patch.object(product_briefs,'urlopen') as call:
            assert product_briefs.generate({'photo_ids':['../file']})[1]==400
            assert product_briefs.generate({**payload,'photo_ids':[file_id]*4})[1]==400
            assert call.call_count==0
        with patch.object(product_briefs,'urlopen',side_effect=HTTPError('https://api.openai.com/v1/responses',429,'rate limit',{},None)) as call:
            assert product_briefs.generate(payload)[1]==502
            assert call.call_count==1
    with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
        assert product_briefs.generate(payload)[1]==503
print('PASS: image request, draft parsing, usage, missing key, invalid IDs, bounded image count, and no automatic retry. No paid API request.')
