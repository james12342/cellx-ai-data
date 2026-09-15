from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import subprocess
pid = subprocess.check_output(['systemctl','show','cellx-extension-api','-p','MainPID','--value'], text=True).strip()
env = dict(p.decode().split('=',1) for p in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if b'=' in p)
path = Path(env.get('WORKFLOW_SCHEDULE_DB', '/opt/cellx-extension-api/workflow-schedules.sqlite3'))
with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
    print('Running jobs:', db.execute("SELECT count(*) FROM runs WHERE status='running'").fetchone()[0])
    for row in db.execute('SELECT next_run FROM schedules WHERE enabled=1 AND next_run IS NOT NULL'):
        print('Seconds until schedule:', round((datetime.fromisoformat(row[0].replace('Z','+00:00'))-datetime.now(timezone.utc)).total_seconds()))
