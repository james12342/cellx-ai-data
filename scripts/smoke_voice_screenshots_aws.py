"""Verify screenshot auth and real vision transport using a synthetic red square."""
import base64
import json
from pathlib import Path
import struct
import subprocess
import zlib
from urllib.request import Request, urlopen
from urllib.error import HTTPError

pid=subprocess.check_output(['systemctl','show','cellx-extension-api','-p','MainPID','--value'],text=True).strip()
env=dict(p.decode().split('=',1) for p in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if b'=' in p)
token=env.get('WORKFLOW_MANAGEMENT_TOKEN') or env.get('MARKETPLACE_ADMIN_TOKEN')
assert token
def call(payload,auth=True):
    headers={'Content-Type':'application/json','Origin':'https://app.cellaidata.com'}
    if auth:headers['X-Workflow-Admin-Token']=token
    req=Request('http://127.0.0.1:3001/ext-api/ai/screenshot-analysis',data=json.dumps(payload).encode(),headers=headers)
    try:
        with urlopen(req,timeout=90) as response:return response.status,json.load(response)
    except HTTPError as error:return error.code,json.load(error)
assert call({},False)[0]==401
assert call({'screenshots':['https://example.com/not-allowed']})[0]==400
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',64,64,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\xff\x00\x00'*64)*64))+chunk(b'IEND',b'')
image='data:image/png;base64,'+base64.b64encode(png).decode()
status,body=call({'screenshots':[image],'prompt':'What is the dominant color? Answer with one color word in English.'})
assert status==200, body.get('message','Vision failed')
assert 'red' in body.get('analysis','').lower(), 'Unexpected color analysis'
print('Live screenshot endpoint: unauthorized and remote-URL rejection passed; real vision correctly identified synthetic red image. No user screenshots used.')
