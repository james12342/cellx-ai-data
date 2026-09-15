import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

report = {}
for url in ['https://www.cellaidata.com/', 'https://app.cellaidata.com/portal/', 'https://www.cellaidata.com/analytics.html', 'https://app.cellaidata.com/agent/', 'https://app.cellaidata.com/data/', 'https://app.cellaidata.com/workflow/', 'https://app.cellaidata.com/']:
    with urlopen(url, timeout=15) as response:
        body = response.read().decode('utf-8')
        report[url] = {'status': response.status, 'final_url': response.url}
        if '/workflow/' in url:
            assert '/agent/' in response.url
        if url != 'https://app.cellaidata.com/':
            assert 'i18n.js?v=20260914-i18n-v1' in body
with urlopen('https://app.cellaidata.com/ext-api/health', timeout=15) as response:
    health = json.load(response)
    assert health['ok'] and health['scheduler']['running']
    report['scheduler_running'] = True
for route in ['data-explorer/catalog', 'agent-schemas/status']:
    try:
        urlopen('https://app.cellaidata.com/ext-api/' + route, timeout=15)
        raise AssertionError('Unauthenticated endpoint accepted')
    except HTTPError as error:
        assert error.code == 401
        report[route] = error.code
legacy = Path('/usr/share/cellx-base-ui/assets/index-DaD6IAmN.js')
if legacy.exists():
    assert hashlib.sha256(legacy.read_bytes()).hexdigest() == 'f53b7ec251b107c8a9e05095cb86dd461842f1d817dcde36646d1dabda7286cd'
    report['legacy_bundle_unchanged'] = True
print(json.dumps(report))
