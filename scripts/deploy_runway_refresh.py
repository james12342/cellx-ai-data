"""Refresh the photo-to-video feature using guarded live-file patches."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / 'outputs/runway-refresh'
STAGE.mkdir(parents=True, exist_ok=True)
HOST = 'ubuntu@44.240.97.37'
OPTIONS = ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-i', 'C:/Users/hibre/Downloads/LightsailDefaultKey-us-west-2.pem']
SSH = ['ssh', *OPTIONS, HOST]
SCP = ['scp', *OPTIONS]
entries = []

def stage_file(folder, name, transform=None):
    target = ('/opt/' if folder.endswith('-api') else '/var/www/') + folder + '/' + name
    exists = subprocess.run(SSH + ['test -f ' + target]).returncode == 0
    before = STAGE / (name + '.before')
    if exists:
        subprocess.run(SCP + [HOST + ':' + target, str(before)], check=True)
    data = transform(before.read_text(encoding='utf-8')) if transform else (ROOT / folder / name).read_text(encoding='utf-8')
    (STAGE / name).write_text(data, encoding='utf-8')
    entries.append({'file': name, 'target': target, 'before': hashlib.sha256(before.read_bytes()).hexdigest() if exists else None,
                    'after': hashlib.sha256((STAGE / name).read_bytes()).hexdigest()})

def patch_server(live):
    local = (ROOT / 'cellx-extension-api/server.py').read_text(encoding='utf-8')
    def method(source):
        cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Handler')
        return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'serve_photo_upload')
    old, new = method(live), method(local)
    lines = live.splitlines(keepends=True)
    lines[old.lineno-1:old.end_lineno] = local.splitlines(keepends=True)[new.lineno-1:new.end_lineno]
    return ''.join(lines)

def patch_index(live):
    for asset in ['workflow-photos.js', 'workflow-video.js', 'workflow-video.css']:
        live, count = re.subn(re.escape(asset) + r'\?v=[^"\s]+', asset + '?v=20260915-ai-brief-v2', live)
        assert count == 1, asset
    return live

def patch_manifest(live):
    data = json.loads(live)
    local = json.loads((ROOT / 'cellx-extension-ui/workflow-templates/manifest.json').read_text())
    entry = next(e for e in local['templates'] if e['file'] == 'runway-product-ad-video-test.json')
    data['templates'] = [e for e in data['templates'] if e['file'] != entry['file']]
    data['templates'].insert(0, entry)
    return json.dumps(data, indent=2) + '\n'

stage_file('cellx-extension-api', 'server.py', patch_server)
for name in ['photo_uploads.py', 'runway_videos.py', 'promo_videos.py', 'video_music.py', 'product_briefs.py', 'requirements-runway.txt']:
    stage_file('cellx-extension-api', name)
for name in ['workflow-photos.js', 'workflow-video.js', 'workflow-video.css']:
    stage_file('cellx-extension-ui', name)
stage_file('cellx-extension-ui', 'index.html', patch_index)
stage_file('cellx-extension-ui/workflow-templates', 'runway-product-ad-video-test.json')
stage_file('cellx-extension-ui/workflow-templates', 'manifest.json', patch_manifest)
# The payload manifest must have a different name from the template catalog.
(STAGE / 'deploy-manifest.json').write_text(json.dumps(entries))
installer = (ROOT / 'scripts/install_photo_uploads.py').read_text()
installer = installer.replace('stage / "manifest.json"', 'stage / "deploy-manifest.json"')
installer = installer.replace('Path("/var/www/cellx-extension-ui")}', 'Path("/var/www/cellx-extension-ui"), Path("/var/www/cellx-extension-ui/workflow-templates")}')
(STAGE / 'install.py').write_text(installer)
remote = subprocess.check_output(SSH + ['mktemp -d /tmp/cellx-runway-refresh-XXXXXXXX'], text=True).strip()
assert remote.startswith('/tmp/cellx-runway-refresh-')
for name in [e['file'] for e in entries] + ['deploy-manifest.json', 'install.py']:
    subprocess.run(SCP + [str(STAGE / name), HOST + ':' + remote + '/' + name], check=True)
subprocess.run(SSH + ['sudo python3 -m pip install --target /opt/cellx-extension-api/runway-sdk -r ' + remote + '/requirements-runway.txt'], check=True)
subprocess.run(SSH + ['sudo python3 ' + remote + '/install.py'], check=True)
subprocess.run(SSH + ["sudo python3 -c \"import sys; sys.path.insert(0, '/opt/cellx-extension-api'); from video_music import PRESETS, make_music; from pathlib import Path; root=Path('/var/www/cellx-extension-ui/music'); root.mkdir(exist_ok=True); [make_music(root/(name+'.wav'), 8, name) for name in PRESETS]\""], check=True)
print('Remote staging:', remote)
