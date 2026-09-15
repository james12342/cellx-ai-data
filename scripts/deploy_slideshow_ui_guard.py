"""Publish the workflow-switch guard without restarting rendering services."""
import hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent.parent
stage=root/'outputs/slideshow-ui-guard';stage.mkdir(parents=True,exist_ok=True)
host='ubuntu@44.240.97.37';key='C:/Users/hibre/Downloads/LightsailDefaultKey-us-west-2.pem'
scp=['scp','-o','BatchMode=yes','-i',key];ssh=['ssh','-o','BatchMode=yes','-i',key,host]
entries=[]
for name in ['index.html','workflow-video.js']:
    target='/var/www/cellx-extension-ui/'+name;before=stage/(name+'.before')
    subprocess.run(scp+[host+':'+target,str(before)],check=True)
    assert before.read_bytes()==(root/'outputs/slideshow-deploy'/name).read_bytes(),'Live file changed'
    if name=='index.html':
        text=before.read_text(encoding='utf-8');assert text.count('workflow-video.js?v=20260914-slideshow-v1')==1
        (stage/name).write_text(text.replace('workflow-video.js?v=20260914-slideshow-v1','workflow-video.js?v=20260914-slideshow-v2'),encoding='utf-8')
    else:(stage/name).write_bytes((root/'cellx-extension-ui'/name).read_bytes())
    entries.append({'file':name,'target':target,'before':hashlib.sha256(before.read_bytes()).hexdigest(),'after':hashlib.sha256((stage/name).read_bytes()).hexdigest()})
(stage/'manifest.json').write_text(json.dumps(entries))
subprocess.run(['node','--check',str(stage/'workflow-video.js')],check=True)
remote=subprocess.check_output(ssh+['mktemp -d /tmp/cellx-video-ui-XXXXXXXX'],text=True).strip()
assert remote.startswith('/tmp/cellx-video-ui-')
for name in ['index.html','workflow-video.js','manifest.json']:subprocess.run(scp+[str(stage/name),host+':'+remote+'/'+name],check=True)
subprocess.run(scp+[str(root/'scripts/install_i18n_deploy.py'),host+':'+remote+'/install.py'],check=True)
subprocess.run(ssh+['sudo python3 '+remote+'/install.py'],check=True)
