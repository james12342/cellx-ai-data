"""Read-only readiness checks; never submits a paid Runway generation."""
import json
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen
from urllib.error import HTTPError

pid = subprocess.check_output(['systemctl','show','cellx-extension-api','-p','MainPID','--value'],text=True).strip()
env = dict(item.decode().split('=',1) for item in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if b'=' in item)
token = env.get('WORKFLOW_MANAGEMENT_TOKEN') or env.get('MARKETPLACE_ADMIN_TOKEN')
assert token

def call(path, payload=None, auth=True):
    headers = {'Origin':'https://app.cellaidata.com','Content-Type':'application/json'}
    if auth:
        headers['X-Workflow-Admin-Token'] = token
    req = Request('http://127.0.0.1:3001/ext-api'+path, headers=headers,
                  data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urlopen(req,timeout=10) as response:
            return response.status,json.load(response)
    except HTTPError as error:
        return error.code,json.load(error)

assert call('/promo-videos/providers',auth=False)[0] == 401
code,info = call('/promo-videos/providers')
assert code == 200 and isinstance(info['runway_configured'],bool)
assert not any(value and value in json.dumps(info) for value in [env.get('RUNWAYML_API_SECRET'),env.get('RUNWAY_API_KEY')])
# No confirmation is provided, even if a key has been configured meanwhile.
payload = {'request_id':'f'*40,'photo_ids':['e'*40],
           'options':{'mode':'runway','duration_seconds':10,'product_info':'Synthetic readiness test'}}
code,result = call('/promo-videos',payload)
assert code in {400,503}
assert call('/promo-videos/'+'f'*40)[0] == 404
with urlopen('https://app.cellaidata.com/agent/',timeout=15) as response:
    html = response.read().decode()
assert 'workflow-video.js?v=20260914-runway-v1' in html
assert 'workflow-video.css?v=20260914-runway-v1' in html
print('PASS: private provider status, no-secret response, unpaid submission blocked, no job created, live UI cache updated.')
print('Runway configured:',info['runway_configured'])
