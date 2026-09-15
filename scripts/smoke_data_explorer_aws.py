"""Read-only candidate/live API smoke. Never prints credentials or record contents."""
import importlib.util
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

pid = subprocess.check_output(['systemctl', 'show', 'cellx-extension-api', '-p', 'MainPID', '--value'], text=True).strip()
assert pid.isdigit() and int(pid) > 0
environment = dict(part.decode().split('=', 1) for part in Path('/proc/' + pid + '/environ').read_bytes().split(b'\0') if b'=' in part)
os.environ.update(environment)
token = environment.get('WORKFLOW_MANAGEMENT_TOKEN') or environment.get('MARKETPLACE_ADMIN_TOKEN')
assert token, 'Admin authentication is not configured'
headers = {'X-Workflow-Admin-Token': token}
live = '--live' in sys.argv
if not live:
    sys.path.insert(0, str(Path(__file__).parent))
    sys.path.append('/opt/cellx-extension-api')
    spec = importlib.util.spec_from_file_location('candidate_server', Path(__file__).with_name('server.py'))
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)

def request(operation, query=None, auth=True, method='GET'):
    query = query or {}
    request_headers = headers if auth else {}
    if not live:
        return server.data_explorer_request(method, '/data-explorer/' + operation, request_headers, {k: [str(v)] for k, v in query.items()})
    url = 'http://127.0.0.1:3001/data-explorer/' + operation + ('?' + urlencode(query) if query else '')
    req = Request(url, headers=request_headers, method=method)
    try:
        with urlopen(req, timeout=15) as response:
            assert response.headers.get('Cache-Control') == 'no-store'
            return json.load(response), response.status
    except HTTPError as error:
        return json.load(error), error.code

report = {'mode': 'live' if live else 'candidate'}
for route in ('status', 'catalog', 'table', 'rows'):
    assert request(route, auth=False)[1] == 401, 'Unauthenticated request accepted'
assert request('catalog', {'company_id': 'admin', 'role': 'admin'}, auth=False)[1] == 401
assert request('catalog', method='POST')[1] == 405
catalog, status = request('catalog')
assert status == 200, 'Catalog failed: ' + str(catalog.get('code', status))
report['physical_tables'] = len(catalog['tables'])
report['planned_tables'] = len(catalog['planned_tables'])
assert all(item['state'] == 'planned' for item in catalog['planned_tables'])
assert all(table['physical_exists'] for table in catalog['tables'])
assert request('rows', {'table': 'x`; DROP TABLE x;'})[1] == 400
assert request('rows', {'table': 'table_that_does_not_exist'})[1] == 404
tables = sorted(catalog['tables'], key=lambda t: (not t['name'].startswith('cx_order'), not t['name'].startswith('cx_'), t['name']))
assert tables, 'No real tables available'
table = tables[0]
metadata, status = request('table', {'table': table['name']})
assert status == 200 and metadata['table']['name'] == table['name']
page, status = request('rows', {'table': table['name'], 'page_size': 2})
assert status == 200, 'Rows failed: ' + str(page.get('code', status))
assert len(page['rows']) <= 2
assert request('rows', {'table': table['name'], 'page_size': 101})[1] == 400
assert request('rows', {'table': table['name'], 'direction': 'asc; select 1'})[1] == 400
for row in page['rows']:
    assert all(row[col['name']] == '[REDACTED]' for col in page['columns'] if col['masked'])
masked = next((col for col in table['columns'] if col['masked']), None)
if masked:
    assert request('rows', {'table': table['name'], 'sort': masked['name']})[1] == 403
report['row_sample_count'] = len(page['rows'])
report['sample_table'] = table['name']
report['read_only'] = page['read_only']
report['auth_and_injection_checks'] = 'passed'
path = Path(environment.get('WORKFLOW_SCHEDULE_DB', '/opt/cellx-extension-api/workflow-schedules.sqlite3'))
if path.exists():
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        report['running_workflows'] = db.execute("SELECT count(*) FROM runs WHERE status='running'").fetchone()[0]
        report['enabled_schedules'] = db.execute('SELECT count(*) FROM schedules WHERE enabled=1').fetchone()[0]
        next_runs = [row[0] for row in db.execute('SELECT next_run FROM schedules WHERE enabled=1 AND next_run IS NOT NULL')]
        if not live:
            assert all(datetime.fromisoformat(value) > datetime.now(timezone.utc) + timedelta(minutes=2) for value in next_runs), 'Schedule due soon: postpone restart'
assert report.get('running_workflows', 0) == 0, 'Active workflow: postpone restart'
print(json.dumps(report))
