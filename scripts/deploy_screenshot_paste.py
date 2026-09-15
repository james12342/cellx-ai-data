"""Deploy only the screenshot composer assets; no API restart."""
import hashlib
import json
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parent.parent
stage=root/'outputs/screenshot-paste-deploy'
stage.mkdir(parents=True,exist_ok=True)
host='ubuntu@44.240.97.37'
key='C:/Users/hibre/Downloads/LightsailDefaultKey-us-west-2.pem'
ssh=['ssh','-o','BatchMode=yes','-i',key,host]
scp=['scp','-o','BatchMode=yes','-i',key]
entries=[]
for name in ['index.html','voice-screenshots.js','voice-screenshots.css']:
    target='/var/www/cellx-extension-ui/'+name
    before=stage/(name+'.before')
    subprocess.run(scp+[host+':'+target,str(before)],check=True)
    if name=='index.html':
        text=before.read_text(encoding='utf-8')
        for asset in ['voice-screenshots.js','voice-screenshots.css']:
            old=asset+'?v=20260914-screenshots-v1'
            assert text.count(old)==1,'Unexpected live screenshot version'
            text=text.replace(old,asset+'?v=20260914-paste-v2')
        (stage/name).write_text(text,encoding='utf-8')
    else:
        expected=root/'outputs/voice-screenshot-deploy'/name
        assert before.read_bytes()==expected.read_bytes(),'Screenshot asset changed since previous deployment'
        (stage/name).write_bytes((root/'cellx-extension-ui'/name).read_bytes())
    entries.append({'file':name,'target':target,'before':hashlib.sha256(before.read_bytes()).hexdigest(),
                    'after':hashlib.sha256((stage/name).read_bytes()).hexdigest()})
(stage/'manifest.json').write_text(json.dumps(entries))
subprocess.run(['node','--check',str(stage/'voice-screenshots.js')],check=True)
remote=subprocess.check_output(ssh+['mktemp -d /tmp/cellx-screenshot-paste-XXXXXXXX'],text=True).strip()
assert remote.startswith('/tmp/cellx-screenshot-paste-')
for name in [e['file'] for e in entries]+['manifest.json']:
    subprocess.run(scp+[str(stage/name),host+':'+remote+'/'+name],check=True)
subprocess.run(scp+[str(root/'scripts/install_i18n_deploy.py'),host+':'+remote+'/install.py'],check=True)
subprocess.run(ssh+['sudo python3 '+remote+'/install.py'],check=True)
