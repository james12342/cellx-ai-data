"""Deploy minimal API extension with active-job checks, backup and health rollback."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import time
from urllib.request import urlopen

stage = Path(__file__).parent
root = Path('/opt/cellx-extension-api')
manifest = json.loads((stage / 'manifest.json').read_text())
assert hashlib.sha256((root / 'server.py').read_bytes()).hexdigest() == manifest['before_server'], 'Live API changed'
for name, digest in manifest['files'].items():
    assert name in {'server.py', 'data_explorer.py'}
    assert hashlib.sha256((stage / name).read_bytes()).hexdigest() == digest
    compile((stage / name).read_text(), name, 'exec')
pid = subprocess.check_output(['systemctl', 'show', 'cellx-extension-api', '-p', 'MainPID', '--value'], text=True).strip()
environment = dict(part.decode().split('=', 1) for part in Path('/proc/' + pid + '/environ').read_bytes().split(b'\0') if b'=' in part)
schedule = Path(environment.get('WORKFLOW_SCHEDULE_DB', str(root / 'workflow-schedules.sqlite3')))
if schedule.exists():
    with sqlite3.connect(schedule.as_uri() + '?mode=ro', uri=True) as db:
        assert db.execute("SELECT count(*) FROM runs WHERE status='running'").fetchone()[0] == 0, 'Workflow running; postpone restart'
        for (next_run,) in db.execute('SELECT next_run FROM schedules WHERE enabled=1 AND next_run IS NOT NULL'):
            assert datetime.fromisoformat(next_run.replace('Z', '+00:00')) > datetime.now(timezone.utc) + timedelta(minutes=2), 'Scheduled job imminent; postpone restart'
backup = Path(tempfile.mkdtemp(prefix='cellx-before-data-api-'))
for name in manifest['files']:
    if (root / name).exists():
        shutil.copy2(root / name, backup / name)

def healthy():
    for _ in range(20):
        try:
            data = json.load(urlopen('http://127.0.0.1:3001/health', timeout=2))
            if data.get('ok') and data.get('scheduler', {}).get('running'):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

try:
    for name in manifest['files']:
        temporary = root / (name + '.data-staging')
        shutil.copyfile(stage / name, temporary)
        os.chmod(temporary, 0o644)
        os.replace(temporary, root / name)
    subprocess.run(['systemctl', 'restart', 'cellx-extension-api'], check=True, timeout=30)
    assert healthy(), 'API health check failed'
except Exception:
    for name in manifest['files']:
        if (backup / name).exists():
            shutil.copy2(backup / name, root / name)
        else:
            (root / name).unlink(missing_ok=True)
    subprocess.run(['systemctl', 'restart', 'cellx-extension-api'], check=True, timeout=30)
    raise
print('Data Explorer API deployed; scheduler healthy. Backup:', backup)
