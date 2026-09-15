"""Deploy the photo-count fix and repair only the verified rejected request."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def install():
    stage = Path(__file__).resolve().parent
    api = Path('/opt/cellx-extension-api')
    sys.path.insert(0, str(api))
    subprocess.run([sys.executable, '-m', 'unittest', 'test_runway_videos'], cwd=stage,
                   env={**os.environ, 'PYTHONPATH': str(api)}, check=True)
    manifest = json.loads((stage / 'manifest.json').read_text())
    for item in manifest:
        assert hashlib.sha256(Path(item['target']).read_bytes()).hexdigest() == item['before'], 'Live code changed'
    import sqlite3
    from datetime import datetime, timezone
    pid = subprocess.check_output(['systemctl', 'show', 'cellx-extension-api', '-p', 'MainPID', '--value'], text=True).strip()
    env = dict(x.decode().split('=', 1) for x in Path('/proc/' + pid + '/environ').read_bytes().split(b'\0') if b'=' in x)
    dbpath = Path(env.get('WORKFLOW_SCHEDULE_DB', str(api / 'workflow-schedules.sqlite3')))
    with sqlite3.connect(dbpath.as_uri() + '?mode=ro', uri=True) as db:
        assert db.execute("SELECT count(*) FROM runs WHERE status='running'").fetchone()[0] == 0, 'Scheduled job running'
        for row in db.execute('SELECT next_run FROM schedules WHERE enabled=1 AND next_run IS NOT NULL'):
            assert (datetime.fromisoformat(row[0].replace('Z', '+00:00')) - datetime.now(timezone.utc)).total_seconds() > 120, 'Schedule imminent'
    video_root = Path(env.get('PROMO_VIDEO_DIR', str(api / 'private-videos')))
    jobs = [(p, json.loads(p.read_text())) for p in video_root.glob('*.json')]
    assert not any(j.get('status') in ('submitting', 'rendering') for p, j in jobs), 'Video job active'
    rejected = [(p, j) for p, j in jobs if j.get('provider') == 'runway' and j.get('created_at') == 1789496207.0622876]
    assert len(rejected) == 1, 'Verified rejected job not found'
    jobpath, job = rejected[0]
    assert job['status'] == 'needs_review' and not job.get('task_id') and job.get('photo_count', 0) > 10
    backup = Path(tempfile.mkdtemp(prefix='cellx-before-runway-photo-fix-'))
    backup.chmod(0o700)
    for item in manifest:
        shutil.copy2(item['target'], backup / item['file'])
    shutil.copy2(jobpath, backup / 'rejected-job.json')
    subprocess.run(['systemctl', 'stop', 'cellx-extension-api'], check=True)
    try:
        for item in manifest:
            target = Path(item['target'])
            temp = target.with_name(target.name + '.photo-fix-staging')
            shutil.copyfile(stage / item['file'], temp)
            temp.chmod(0o644)
            os.replace(temp, target)
        job.update(status='failed', provider_http_status=400,
                   message='Runway rejected this request: more than 10 reference photos. No generation task was created. Start a new generation with at most 10 references.',
                   recovery_reason='Confirmed HTTP 400 productImages maximum 10 in Runway request history supplied by account owner.')
        temp = jobpath.with_suffix('.recovered')
        temp.write_text(json.dumps(job))
        temp.chmod(0o600)
        os.replace(temp, jobpath)
        subprocess.run(['systemctl', 'start', 'cellx-extension-api'], check=True)
        subprocess.run(['curl', '--fail', '--silent', '--retry', '8', '--retry-connrefused', '--retry-delay', '1', 'http://127.0.0.1:3001/health'], check=True)
    except Exception:
        for item in manifest:
            shutil.copy2(backup / item['file'], item['target'])
        shutil.copy2(backup / 'rejected-job.json', jobpath)
        subprocess.run(['systemctl', 'restart', 'cellx-extension-api'], check=True)
        raise
    print('\nPublished photo-count fix; verified rejected job marked failed. Backup:', backup)


def deploy():
    root = Path(__file__).resolve().parent.parent
    stage = root / 'outputs/runway-photo-fix'
    stage.mkdir(parents=True, exist_ok=True)
    host = 'ubuntu@44.240.97.37'
    opts = ['-o', 'BatchMode=yes', '-i', 'C:/Users/hibre/Downloads/LightsailDefaultKey-us-west-2.pem']
    ssh, scp = ['ssh', *opts, host], ['scp', *opts]
    manifest = []
    for name, directory in [('runway_videos.py', 'cellx-extension-api'), ('workflow-video.js', 'cellx-extension-ui'), ('index.html', 'cellx-extension-ui')]:
        target = ('/opt/' if directory.endswith('api') else '/var/www/') + directory + '/' + name
        before = stage / (name + '.before')
        subprocess.run(scp + [host + ':' + target, str(before)], check=True)
        data = (root / directory / name).read_bytes()
        if name == 'index.html':
            content, count = re.subn(r'workflow-video\.js\?v=[^"\s]+', 'workflow-video.js?v=20260915-photo-count-fix', before.read_text(encoding='utf-8'))
            assert count == 1
            data = content.encode()
        (stage / name).write_bytes(data)
        manifest.append({'file': name, 'target': target, 'before': hashlib.sha256(before.read_bytes()).hexdigest()})
    (stage / 'manifest.json').write_text(json.dumps(manifest))
    shutil.copy2(root / 'cellx-extension-api/test_runway_videos.py', stage / 'test_runway_videos.py')
    shutil.copy2(__file__, stage / 'install.py')
    remote = subprocess.check_output(ssh + ['mktemp -d /tmp/cellx-runway-photo-fix-XXXXXXXX'], text=True).strip()
    assert remote.startswith('/tmp/cellx-runway-photo-fix-')
    for name in [i['file'] for i in manifest] + ['manifest.json', 'test_runway_videos.py', 'install.py']:
        subprocess.run(scp + [str(stage / name), host + ':' + remote + '/' + name], check=True)
    subprocess.run(ssh + ['sudo python3 ' + remote + '/install.py --install'], check=True)


def repair_index_encoding():
    root = Path(__file__).resolve().parent.parent
    stage = root / 'outputs/runway-photo-fix'
    host = 'ubuntu@44.240.97.37'
    opts = ['-o', 'BatchMode=yes', '-i', 'C:/Users/hibre/Downloads/LightsailDefaultKey-us-west-2.pem']
    ssh, scp = ['ssh', *opts, host], ['scp', *opts]
    target = '/var/www/cellx-extension-ui/index.html'
    current = stage / 'index.encoding-before'
    subprocess.run(scp + [host + ':' + target, str(current)], check=True)
    content, count = re.subn(r'workflow-video\.js\?v=[^"\s]+', 'workflow-video.js?v=20260915-photo-count-fix', (stage / 'index.html.before').read_text(encoding='utf-8'))
    assert count == 1
    data = content.encode('utf-8')
    (stage / 'index.html').write_bytes(data)
    entry = {'file': 'index.html', 'target': target, 'before': hashlib.sha256(current.read_bytes()).hexdigest(), 'after': hashlib.sha256(data).hexdigest()}
    (stage / 'manifest.json').write_text(json.dumps([entry]), encoding='utf-8')
    remote = subprocess.check_output(ssh + ['mktemp -d /tmp/cellx-index-encoding-XXXXXXXX'], text=True).strip()
    for name in ['index.html', 'manifest.json']:
        subprocess.run(scp + [str(stage / name), host + ':' + remote + '/' + name], check=True)
    subprocess.run(scp + [str(root / 'scripts/install_i18n_deploy.py'), host + ':' + remote + '/install.py'], check=True)
    subprocess.run(ssh + ['sudo python3 ' + remote + '/install.py'], check=True)


if __name__ == '__main__':
    if '--repair-index' in sys.argv:
        repair_index_encoding()
    else:
        install() if '--install' in sys.argv else deploy()
