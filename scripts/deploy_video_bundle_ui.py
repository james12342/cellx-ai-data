"""Deploy only automatic video-node companion UI changes."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

root=Path(__file__).resolve().parent.parent
stage=root/'outputs/video-bundle-ui'
stage.mkdir(parents=True,exist_ok=True)
host='ubuntu@44.240.97.37'
opts=['-o','BatchMode=yes','-o','ConnectTimeout=15','-i','C:/Users/hibre/Downloads/LightsailDefaultKey-us-west-2.pem']
ssh=['ssh',*opts,host]
scp=['scp',*opts]
manifest=[]
for name in ['app.js','workflow-video.js','workflow-video.css','workflow-photos.js','index.html']:
    target='/var/www/cellx-extension-ui/'+name
    before=stage/(name+'.before')
    subprocess.run(scp+[host+':'+target,str(before)],check=True)
    live=before.read_text(encoding='utf-8')
    local=(root/'cellx-extension-ui'/name).read_text(encoding='utf-8')
    if name=='app.js':
        start='function addCatalogNode(item, x, y) {'
        end='function nextCanvasSpot() {'
        assert live.count(start)==local.count(start)==1
        old=live[live.index(start):live.index(end)]
        new=local[local.index(start):local.index(end)]
        live=live.replace(old,new)
        entry=next(line for line in local.splitlines() if '{ name: "Video Generation",' in line)
        if '{ name: "Video Generation",' not in live:
            anchor='    group: "Agent Skills & Tools",\n    children: [\n'
            assert live.count(anchor)==1
            live=live.replace(anchor,anchor+entry+'\n')
        data=live
    elif name=='index.html':
        data=live
        for asset in ['app.js','workflow-video.js','workflow-video.css','workflow-photos.js']:
            data,count=re.subn(r'(?<=/)' + re.escape(asset)+r'\?v=[^"\s]+',asset+'?v=20260915-copy-photos-v1',data)
            assert count==1,asset
    else:
        data=local
    (stage/name).write_text(data,encoding='utf-8')
    manifest.append({'file':name,'target':target,'before':hashlib.sha256(before.read_bytes()).hexdigest(),'after':hashlib.sha256((stage/name).read_bytes()).hexdigest()})
(stage/'manifest.json').write_text(json.dumps(manifest))
remote=subprocess.check_output(ssh+['mktemp -d /tmp/cellx-video-bundle-XXXXXXXX'],text=True).strip()
assert remote.startswith('/tmp/cellx-video-bundle-')
for name in [e['file'] for e in manifest]+['manifest.json']:
    subprocess.run(scp+[str(stage/name),host+':'+remote+'/'+name],check=True)
subprocess.run(scp+[str(root/'scripts/install_i18n_deploy.py'),host+':'+remote+'/install.py'],check=True)
subprocess.run(ssh+['sudo python3 '+remote+'/install.py'],check=True)
