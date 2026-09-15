"""Read cloud job state without displaying credentials or uploaded content."""
import json
from pathlib import Path
import subprocess
import sys
import os

pid = subprocess.check_output(['systemctl', 'show', 'cellx-extension-api', '-p', 'MainPID', '--value'], text=True).strip()
env = dict(item.decode().split('=', 1) for item in Path('/proc/' + pid + '/environ').read_bytes().split(b'\0') if b'=' in item)
print('service_running:', pid != '0')
print('runway_key_present:', bool(env.get('RUNWAYML_API_SECRET') or env.get('RUNWAY_API_KEY')))
root = Path(env.get('PROMO_VIDEO_DIR', '/opt/cellx-extension-api/private-videos'))
for path in sorted(root.glob('*.json')):
    job = json.loads(path.read_text())
    print(json.dumps({k: job.get(k) for k in ('status', 'provider', 'message', 'created_at')}, ensure_ascii=True))
    print('task_id_present:', bool(job.get('task_id')))
sys.path.insert(0, '/opt/cellx-extension-api/runway-sdk')
os.environ.update({k: v for k, v in env.items() if k in ('RUNWAYML_API_SECRET', 'RUNWAY_API_KEY')})
try:
    from runwayml import RunwayML
    client = RunwayML(max_retries=0)
    print('sdk_client_initialized:', True)
    client.close()
except Exception as error:
    print('sdk_initialization_error_type:', type(error).__name__)
