"""Deploy only the slideshow feature against captured current AWS sources."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parent.parent
stage=root/'outputs/slideshow-deploy';stage.mkdir(parents=True,exist_ok=True)
host='ubuntu@44.240.97.37';key='C:/Users/hibre/Downloads/LightsailDefaultKey-us-west-2.pem'
ssh=['ssh','-o','BatchMode=yes','-i',key,host];scp=['scp','-o','BatchMode=yes','-i',key]
def once(text,old,new):
    assert text.count(old)==1,'Unexpected live anchor: '+old[:70]
    return text.replace(old,new)
entries=[]
for folder,name,target in [('cellx-extension-api','server.py','/opt/cellx-extension-api/server.py'),('cellx-extension-ui','app.js','/var/www/cellx-extension-ui/app.js'),('cellx-extension-ui','index.html','/var/www/cellx-extension-ui/index.html')]:
    before=stage/(name+'.before');subprocess.run(scp+[host+':'+target,str(before)],check=True)
    text=before.read_text(encoding='utf-8');local=(root/folder/name).read_text(encoding='utf-8')
    if name=='server.py':
        tree=ast.parse(local);handler=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Handler')
        method=next(n for n in handler.body if isinstance(n,ast.FunctionDef) and n.name=='serve_promo_video')
        segment='\n'.join(local.splitlines()[method.lineno-1:method.end_lineno])+'\n\n'
        anchor='class Handler(BaseHTTPRequestHandler):\n';text=once(text,anchor,anchor+segment)
        for method in ['do_PUT','do_GET','do_POST']:
            anchor=f'    def {method}(self):\n'
            text=once(text,anchor,anchor+'        if normalize_api_path(urlparse(self.path).path).startswith("/promo-videos"):\n            return self.serve_promo_video()\n')
        compile(text,name,'exec')
    elif name=='app.js':
        anchor='async function testNodeIntegration(node, execute = false) {\n'
        text=once(text,anchor,anchor+'  if (window.WorkflowVideo?.isNode(node)) return window.WorkflowVideo.test(node);\n')
        anchor='    await testNodeIntegration(node, true);\n'
        text=once(text,anchor,anchor+'    if (window.WorkflowVideo?.isNode(node)) {\n      window.WorkflowVideo.pauseFollowing(node);\n      break;\n    }\n')
        anchor='function render() {\n';text=once(text,anchor,anchor+'  window.WorkflowVideo?.render();\n')
    else:
        text=once(text,'./app.js?v=20260914-screenshots-v1','./app.js?v=20260914-slideshow-v1')
        text=once(text,'</body>','  <link rel="stylesheet" href="./workflow-video.css?v=20260914-slideshow-v1">\n  <script src="./workflow-video.js?v=20260914-slideshow-v1"></script>\n</body>')
    (stage/name).write_text(text,encoding='utf-8')
    entries.append({'file':name,'target':target,'before':hashlib.sha256(before.read_bytes()).hexdigest()})
for folder,name,dest in [('cellx-extension-api','promo_videos.py','/opt/cellx-extension-api/'),('cellx-extension-ui','workflow-video.js','/var/www/cellx-extension-ui/'),('cellx-extension-ui','workflow-video.css','/var/www/cellx-extension-ui/')]:
    (stage/name).write_bytes((root/folder/name).read_bytes());entries.append({'file':name,'target':dest+name,'before':None})
for entry in entries:entry['after']=hashlib.sha256((stage/entry['file']).read_bytes()).hexdigest()
(stage/'manifest.json').write_text(json.dumps(entries))
for name in ['app.js','workflow-video.js']:subprocess.run(['node','--check',str(stage/name)],check=True)
remote=subprocess.check_output(ssh+['mktemp -d /tmp/cellx-slideshow-deploy-XXXXXXXX'],text=True).strip()
assert remote.startswith('/tmp/cellx-slideshow-deploy-')
for name in [e['file'] for e in entries]+['manifest.json']:subprocess.run(scp+[str(stage/name),host+':'+remote+'/'+name],check=True)
subprocess.run(scp+[str(root/'scripts/install_photo_uploads.py'),host+':'+remote+'/install.py'],check=True)
subprocess.run(ssh+['sudo python3 '+remote+'/install.py'],check=True)
