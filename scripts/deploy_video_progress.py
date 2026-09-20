"""Publish progress UI only; never restart or submit video jobs."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parent.parent
stage = root / 'outputs/video-progress'
stage.mkdir(parents=True, exist_ok=True)
host = 'ubuntu@44.240.97.37'
opts = ['-o', 'BatchMode=yes', '-i', 'C:/Users/hibre/Downloads/LightsailDefaultKey-us-west-2.pem']
ssh, scp = ['ssh', *opts, host], ['scp', *opts]
manifest = []
for name in ['workflow-video.js', 'workflow-video.css', 'index.html']:
    target = '/var/www/cellx-extension-ui/' + name
    before = stage / (name + '.before')
    subprocess.run(scp + [host + ':' + target, str(before)], check=True)
    if name == 'index.html':
        content = before.read_text(encoding='utf-8')
        for asset in ['workflow-video.js', 'workflow-video.css']:
            content, count = re.subn(re.escape(asset) + r'\?v=[^"\s]+', asset + '?v=20260915-dictation-v1', content)
            assert count == 1
        data = content.encode('utf-8')
    else:
        data = (root / 'cellx-extension-ui' / name).read_bytes()
    (stage / name).write_bytes(data)
    manifest.append({'file': name, 'target': target, 'before': hashlib.sha256(before.read_bytes()).hexdigest(), 'after': hashlib.sha256(data).hexdigest()})
(stage / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
remote = subprocess.check_output(ssh + ['mktemp -d /tmp/cellx-video-progress-XXXXXXXX'], text=True).strip()
assert remote.startswith('/tmp/cellx-video-progress-')
for name in [e['file'] for e in manifest] + ['manifest.json']:
    subprocess.run(scp + [str(stage / name), host + ':' + remote + '/' + name], check=True)
subprocess.run(scp + [str(root / 'scripts/install_i18n_deploy.py'), host + ':' + remote + '/install.py'], check=True)
subprocess.run(ssh + ['sudo python3 ' + remote + '/install.py'], check=True)
