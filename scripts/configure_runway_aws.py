"""Send the existing local Runway credential over SSH stdin, never argv."""
from pathlib import Path
import re
import shlex
import subprocess

root = Path(__file__).resolve().parent.parent
source = (root / 'runway_api.txt').read_text(encoding='utf-8-sig').replace('\\_', '_')
keys = re.findall(r'key_[a-fA-F0-9]{100,}', source)
assert len(keys) == 1, 'Expected one Runway credential in the local key file'
remote_code = '''
from pathlib import Path
import json, os, re, subprocess, sys, time
from urllib.request import urlopen
secret = sys.stdin.read().strip()
assert re.fullmatch(r'key_[a-fA-F0-9]{100,}', secret)
folder = Path('/etc/cellaidata')
folder.mkdir(mode=0o700, exist_ok=True)
dest = folder / 'runway.env'
fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as stream:
    stream.write('RUNWAYML_API_SECRET=' + secret + '\\n')
dest.chmod(0o600)
drop = Path('/etc/systemd/system/cellx-extension-api.service.d')
drop.mkdir(parents=True, exist_ok=True)
(drop / '70-runway.conf').write_text('[Service]\\nEnvironmentFile=/etc/cellaidata/runway.env\\n')
subprocess.run(['systemctl','daemon-reload'], check=True)
subprocess.run(['systemctl','restart','cellx-extension-api'], check=True)
for attempt in range(30):
    try:
        with urlopen('http://127.0.0.1:3001/health', timeout=2) as response:
            health = json.load(response)
        if health.get('ok') and health.get('scheduler', {}).get('running'):
            print('Runway credential configured; service and scheduler healthy.')
            break
    except Exception:
        pass
    time.sleep(.5)
else:
    raise RuntimeError('Service health check failed')
'''
subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
                '-i', 'C:/Users/hibre/Downloads/LightsailDefaultKey-us-west-2.pem',
                'ubuntu@44.240.97.37', 'sudo python3 -c ' + shlex.quote(remote_code)],
               input=keys[0], text=True, check=True)
