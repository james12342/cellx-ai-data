"""Deploy budget video providers with live hashes, backups and active-job guard."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parent.parent
STAGE=ROOT/'outputs/budget-deploy'
STAGE.mkdir(parents=True,exist_ok=True)
HOST='ubuntu@44.240.97.37'
ARGS=['-o','BatchMode=yes','-o','ConnectTimeout=15','-i','C:/Users/hibre/Downloads/LightsailDefaultKey-us-west-2.pem']
SSH=['ssh',*ARGS,HOST]
SCP=['scp',*ARGS]
entries=[]
for folder,names in [('cellx-extension-api',['budget_videos.py','runway_videos.py','promo_videos.py']),('cellx-extension-ui',['workflow-video.js','workflow-video.css','index.html'])]:
    for name in names:
        target=('/opt/' if folder.endswith('-api') else '/var/www/')+folder+'/'+name
        before=STAGE/(name+'.before')
        exists=subprocess.run(SSH+['test -f '+target]).returncode==0
        if exists:subprocess.run(SCP+[HOST+':'+target,str(before)],check=True)
        data=(ROOT/folder/name).read_bytes() if name!='index.html' else before.read_bytes()
        if name=='index.html':
            content=data.decode()
            for asset in ['workflow-video.js','workflow-video.css']:
                content,count=re.subn(re.escape(asset)+r'\?v=[^"\s]+',asset+'?v=20260915-budget-models-v1',content)
                assert count==1
            data=content.encode()
        (STAGE/name).write_bytes(data)
        entries.append(dict(file=name,target=target,before=hashlib.sha256(before.read_bytes()).hexdigest() if exists else None,after=hashlib.sha256(data).hexdigest()))
(STAGE/'manifest.json').write_text(json.dumps(entries))
installer=(ROOT/'scripts/install_photo_uploads.py').read_text()
anchor='backup = Path(tempfile.mkdtemp(prefix="cellx-before-photos-"))'
guard='''video_root=Path(env.get('PROMO_VIDEO_DIR','/opt/cellx-extension-api/private-videos'))
for record in video_root.glob('*.json'):
    job=json.loads(record.read_text())
    assert job.get('status') not in {'submitting','rendering'}, 'Video still running; deploy after it completes'
'''
assert anchor in installer
(STAGE/'install.py').write_text(installer.replace(anchor,guard+anchor))
remote=subprocess.check_output(SSH+['mktemp -d /tmp/cellx-budget-XXXXXXXX'],text=True).strip()
assert remote.startswith('/tmp/cellx-budget-')
for name in [e['file'] for e in entries]+['manifest.json','install.py']:
    subprocess.run(SCP+[str(STAGE/name),HOST+':'+remote+'/'+name],check=True)
subprocess.run(SSH+['sudo python3 '+remote+'/install.py'],check=True)
print('Budget models deployed. No generation submitted.')
