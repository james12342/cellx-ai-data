"""Live private API smoke: synthetic image and short narration; no paid models."""
import base64
import json
from pathlib import Path
import secrets
import struct
import subprocess
import time
from urllib.request import Request,urlopen
import zlib

pid=subprocess.check_output(['systemctl','show','cellx-extension-api','-p','MainPID','--value'],text=True).strip()
env=dict(p.decode().split('=',1) for p in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if b'=' in p)
token=env.get('WORKFLOW_MANAGEMENT_TOKEN') or env.get('MARKETPLACE_ADMIN_TOKEN')
base='https://app.cellaidata.com/ext-api'
def request(path,method='GET',body=None):
    req=Request(base+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'X-Workflow-Admin-Token':token,'Content-Type':'application/json'})
    with urlopen(req,timeout=30) as response:return json.load(response)

info=request('/promo-videos/providers')
assert info['economy']['renderer'] and info['economy']['voice']
def chunk(kind,data):return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',256,256,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\x40\x70\xa0'*256)*256))+chunk(b'IEND',b'')
photo=request('/photo-uploads','POST',{'name':'economy-test.png','mime_type':'image/png','data':base64.b64encode(png).decode()})['file']['id']
job=None
try:
    body=dict(request_id=secrets.token_hex(20),photo_ids=[photo],options=dict(mode='economy',duration_seconds=15,voice='en-female',aspect_ratio='1:1',narration='给生活留一点美好的时间。\n使用自己的照片，讲述你的故事。',brand='CELL AI',cta='Explore your ideas',music_preset='default',music_volume=.15))
    job=request('/promo-videos','POST',body)
    assert request('/promo-videos','POST',body)['id']==job['id']
    deadline=time.monotonic()+300
    while job['status']=='rendering' and time.monotonic()<deadline:
        time.sleep(3);job=request('/promo-videos/'+job['id'])
    assert job['status']=='completed',job
    assert job['options']['voice']=='zh-female'
    video=Path('/opt/cellx-extension-api/private-videos')/(job['id']+'.mp4')
    result=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
    assert any(s['codec_type']=='audio' for s in result['streams'])
    assert any(s.get('width')==720 and s.get('height')==720 for s in result['streams'])
    assert 14.9<=float(result['format']['duration'])<=60.1
    print('PASS: live HTTPS upload → economy job → Chinese narration with automatic voice correction → square video; duplicate request reused same job.')
finally:
    if job and job['status'] in {'completed','failed'}:request('/promo-videos/'+job['id'],'DELETE')
    request('/photo-uploads/'+photo,'DELETE')
for path in ['/workflow/','/agent/']:
    html=urlopen('https://app.cellaidata.com'+path,timeout=20).read().decode()
    assert 'workflow-video.js?v=20260915-economy-ad-v2' in html
catalog=json.load(urlopen('https://app.cellaidata.com/agent/workflow-templates/manifest.json',timeout=20))
assert any(e['file']=='economy-product-ad.json' for e in catalog['templates'])
print('PASS: both public entry points and economy template. Temporary test records removed.')
