"""Run with sudo on AWS: create/check/disable an isolated, side-effect-free schedule."""
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

state_file = pathlib.Path('/tmp/cellx-daily-scheduler-smoke.json')
pid = subprocess.check_output(['systemctl', 'show', 'cellx-extension-api', '--property=MainPID', '--value'], text=True).strip()
env = dict(part.split(b'=', 1) for part in pathlib.Path(f'/proc/{pid}/environ').read_bytes().split(b'\0') if b'=' in part)
token = (env.get(b'WORKFLOW_MANAGEMENT_TOKEN') or env.get(b'MARKETPLACE_ADMIN_TOKEN') or b'').decode()
if not token:
    raise SystemExit('Workflow management token is not configured.')


def request(path, data=None):
    headers = {'X-Workflow-Admin-Token': token, 'Content-Type': 'application/json'}
    with urlopen(Request('http://127.0.0.1:3001' + path, data=json.dumps(data).encode() if data is not None else None, headers=headers), timeout=15) as response:
        return json.load(response)


mode = sys.argv[1]
if mode == 'create':
    now = datetime.now(timezone.utc)
    due = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    workflow = {
        'id': 'scheduler-smoke-' + now.strftime('%Y%m%d%H%M%S'), 'name': 'Scheduler verification (no external calls)',
        'nodes': [
            {'id': 'trigger', 'name': 'Daily Schedule', 'type': 'trigger', 'action': 'cron', 'integrationSettings': {'schedule': f'{due.minute} {due.hour} * * *', 'timezone': 'UTC', 'scheduleEnabled': 'true'}},
            {'id': 'transform', 'name': 'Build test row', 'type': 'tool', 'action': '/ext-api/tools/json-transform', 'integrationSettings': {'sourcePath': 'previous_step', 'transformMapping': 'run_id <- {{runId}}\nsource <- {{source}}', 'outputMode': 'rows'}},
            {'id': 'log', 'name': 'Write run history', 'type': 'log', 'action': 'cx_workflow_log', 'integrationSettings': {}},
        ],
        'links': [{'from': 'trigger', 'to': 'transform'}, {'from': 'transform', 'to': 'log'}],
    }
    state_file.write_text(json.dumps(workflow))
    data = request('/workflow-schedules/save', {'workflow': workflow})
    print(json.dumps({'saved': data['ok'], 'id': workflow['id'], 'nextRun': data['schedule']['nextRun'], 'scheduler': data['scheduler']}))
elif mode in {'check', 'disable'}:
    workflow = json.loads(state_file.read_text())
    if mode == 'disable':
        workflow['nodes'][0]['integrationSettings']['scheduleEnabled'] = 'false'
        data = request('/workflow-schedules/save', {'workflow': workflow})
    else:
        data = request('/workflow-schedules?id=' + workflow['id'])
    schedule = data['schedule']
    print(json.dumps({'enabled': schedule['enabled'], 'scheduler': data['scheduler'], 'runs': schedule['runs']}, indent=2))
else:
    raise SystemExit('Expected create, check or disable.')
