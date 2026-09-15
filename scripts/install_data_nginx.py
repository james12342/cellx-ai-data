from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

stage = Path(__file__).parent
target = Path('/etc/nginx/conf.d/cellx.base.nginx.http.conf')
manifest = json.loads((stage / 'nginx-manifest.json').read_text())
assert hashlib.sha256(target.read_bytes()).hexdigest() == manifest['before'], 'Live Nginx changed'
assert hashlib.sha256((stage / 'nginx.conf').read_bytes()).hexdigest() == manifest['after']
backup = Path(tempfile.mkdtemp(prefix='cellx-before-data-nginx-')) / 'nginx.conf'
shutil.copy2(target, backup)
try:
    shutil.copyfile(stage / 'nginx.conf', target)
    subprocess.run(['nginx', '-t'], check=True, timeout=10)
    subprocess.run(['systemctl', 'reload', 'nginx'], check=True, timeout=15)
except Exception:
    shutil.copy2(backup, target)
    subprocess.run(['nginx', '-t'], check=True, timeout=10)
    subprocess.run(['systemctl', 'reload', 'nginx'], check=True, timeout=15)
    raise
print('Added /data/ only; legacy root unchanged. Backup:', backup)
