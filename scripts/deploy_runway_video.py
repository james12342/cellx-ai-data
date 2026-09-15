"""Deploy only the reviewed video feature files; preserve other live changes."""
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
stage = root / 'outputs/runway-video-deploy'
stage.mkdir(parents=True, exist_ok=True)
host = 'ubuntu@44.240.97.37'
key = 'C:/Users/hibre/Downloads/LightsailDefaultKey-us-west-2.pem'
scp = ['scp', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-i', key]
ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-i', key, host]
entries = []
for name, folder, baseline in [
    ('promo_videos.py', 'cellx-extension-api', 'outputs/slideshow-deploy'),
    ('runway_videos.py', 'cellx-extension-api', None),
    ('requirements-runway.txt', 'cellx-extension-api', None),
    ('workflow-video.js', 'cellx-extension-ui', 'outputs/slideshow-ui-guard'),
    ('workflow-video.css', 'cellx-extension-ui', 'outputs/slideshow-deploy'),
    ('index.html', 'cellx-extension-ui', 'outputs/slideshow-ui-guard'),
]:
    target = ('/opt/' if folder.endswith('api') else '/var/www/') + folder + '/' + name
    before = stage / (name + '.before')
    if baseline:
        subprocess.run(scp + [host + ':' + target, str(before)], check=True)
        assert before.read_bytes() == (root / baseline / name).read_bytes(), 'Live file changed: ' + name
        old_hash = hashlib.sha256(before.read_bytes()).hexdigest()
    else:
        subprocess.run(ssh + ['test ! -e ' + target], check=True)
        old_hash = None
    if name == 'index.html':
        text = before.read_text(encoding='utf-8')
        for old in ['workflow-video.js?v=20260914-slideshow-v2', 'workflow-video.css?v=20260914-slideshow-v1']:
            assert text.count(old) == 1
            text = text.replace(old, old.split('?')[0] + '?v=20260914-runway-v1')
        (stage / name).write_text(text, encoding='utf-8')
    else:
        (stage / name).write_bytes((root / folder / name).read_bytes())
    entries.append({'file': name, 'target': target, 'before': old_hash,
                    'after': hashlib.sha256((stage / name).read_bytes()).hexdigest()})
(stage / 'manifest.json').write_text(json.dumps(entries))
subprocess.run(['node', '--check', str(stage / 'workflow-video.js')], check=True)
remote = subprocess.check_output(ssh + ['mktemp -d /tmp/cellx-runway-XXXXXXXX'], text=True).strip()
assert remote.startswith('/tmp/cellx-runway-')
for name in [e['file'] for e in entries] + ['manifest.json']:
    subprocess.run(scp + [str(stage / name), host + ':' + remote + '/' + name], check=True)
subprocess.run(scp + [str(root / 'scripts/install_photo_uploads.py'), host + ':' + remote + '/install.py'], check=True)
subprocess.run(ssh + ['sudo python3 -m pip install -r ' + remote + '/requirements-runway.txt && sudo python3 ' + remote + '/install.py'], check=True)
