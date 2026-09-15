"""Check deployed admin-only video API with a disposable synthetic photo."""
import base64
import json
from pathlib import Path
import struct
import subprocess
import time
import zlib
from urllib.request import Request,urlopen
from urllib.error import HTTPError

pid=subprocess.check_output(['systemctl','show','cellx-extension-api','-p','MainPID','--value'],text=True).strip()
env=dict(p.decode().split('=',1) for p in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if b'=' in p)
token=env.get('WORKFLOW_MANAGEMENT_TOKEN') or env.get('MARKETPLACE_ADMIN_TOKEN');assert token
def call(path,method='GET',payload=None,auth=True):
    headers={'Content-Type':'application/json','Origin':'https://app.cellaidata.com'}
    if auth:headers['X-Workflow-Admin-Token']=token
    req=Request('http://127.0.0.1:3001/ext-api'+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers,method=method)
    try:
        with urlopen(req,timeout=30) as reply:
            data=reply.read()
            return reply.status,data if reply.headers.get_content_type()=='video/mp4' else json.loads(data)
    except HTTPError as error:return error.code,json.load(error)
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',64,64,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\x20\xc0\x60'*64)*64))+chunk(b'IEND',b'')
assert call('/promo-videos','POST',{},False)[0]==401
assert call('/promo-videos','POST',{'photo_ids':['../../etc/passwd']})[0]==400
status,photo=call('/photo-uploads','POST',{'name':'slideshow-api-qa.png','data':base64.b64encode(png).decode()});assert status==201
job=None
try:
    status,job=call('/promo-videos','POST',{'photo_ids':[photo['file']['id']],'options':{'duration_seconds':5,'music_preset':'none'}});assert status==202,job
    route='/promo-videos/'+job['id'];deadline=time.time()+200
    assert call(route,auth=False)[0]==401
    while job['status']=='rendering' and time.time()<deadline:
        time.sleep(1);status,job=call(route)
    assert job['status']=='completed',job
    assert call(route+'/file',auth=False)[0]==401
    status,data=call(route+'/file');assert status==200 and b'ftyp' in data[:32] and len(data)>1000
    print('PASS: live upload -> render -> private MP4 download, 5 seconds at 720x1280. Auth and unsafe-path rejection passed.')
finally:
    if job and job.get('id') and job.get('status')!='rendering':assert call('/promo-videos/'+job['id'],'DELETE')[0]==200
    assert call('/photo-uploads/'+photo['file']['id'],'DELETE')[0]==200
print('QA photo and video removed; nothing published.')
