"""Patch the live AWS version without deploying unrelated local edits."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent.parent
STAGE=ROOT/'outputs/voice-screenshot-deploy'
STAGE.mkdir(parents=True,exist_ok=True)
HOST='ubuntu@44.240.97.37'
KEY='C:/Users/hibre/Downloads/LightsailDefaultKey-us-west-2.pem'
SSH=['ssh','-o','BatchMode=yes','-i',KEY,HOST]
SCP=['scp','-o','BatchMode=yes','-i',KEY]
def once(text,old,new):
    assert text.count(old)==1, 'Live anchor changed: '+old[:80]
    return text.replace(old,new)
entries=[]
for folder,name,target in [('cellx-extension-api','server.py','/opt/cellx-extension-api/server.py'),
                           ('cellx-extension-ui','app.js','/var/www/cellx-extension-ui/app.js'),
                           ('cellx-extension-ui','index.html','/var/www/cellx-extension-ui/index.html')]:
    before=STAGE/(name+'.before')
    subprocess.run(SCP+[HOST+':'+target,str(before)],check=True)
    text=before.read_text(encoding='utf-8')
    local=(ROOT/folder/name).read_text(encoding='utf-8')
    if name=='server.py':
        start='def ai_workflow_builder(payload):\n'
        added=local.split(start,1)[1].split('    prompt =',1)[0]
        text=once(text,start,start+added)
        old='            "input": json.dumps(ai_workflow_context(user_input), ensure_ascii=False),\n'
        new=local[local.index('            "input": ([{"role": "user"'):local.index('            "text": {"format": {"type": "json_object"}}')]
        text=once(text,old,new)
        start='    def do_POST(self):\n        path = normalize_api_path(urlparse(self.path).path)\n'
        guard=local.split(start,1)[1].split('        if path.startswith("/photo-uploads"):',1)[0]
        text=once(text,start,start+guard)
        old='        elif path == "/ai/realtime-session":\n'
        addition=local[local.index('        elif path == "/ai/screenshot-analysis":'):local.index(old)]
        text=once(text,old,addition+old)
        compile(text,name,'exec')
    elif name=='app.js':
        old='  document.getElementById("voiceSendBtn").disabled = !connected;\n'
        text=once(text,old,old+'  window.VoiceScreenshots?.render();\n')
        old='    body: JSON.stringify({ prompt: request, currentWorkflow: aiSafeContext(current), availableNodes: nodeCatalog }),'
        text=once(text,old,'    body: JSON.stringify({ prompt: request, currentWorkflow: aiSafeContext(current), availableNodes: nodeCatalog, screenshots: window.VoiceScreenshots?.images() || [] }),')
        old='document.getElementById("voiceSendBtn")?.addEventListener("click", () => {\n'
        text=once(text,old,old+'  if (window.VoiceScreenshots?.images().length) { window.VoiceScreenshots.send(); return; }\n')
    else:
        old='<button id="voiceListenBtn" type="button" data-i18n="Connect Voice">Connect Voice</button>'
        text=once(text,old,old+'\n                <button id="voiceScreenshotBtn" type="button">Upload Screenshot</button>')
        old='<span id="aiVoiceStatus">Ready.</span>'
        text=once(text,old,'<div id="voiceScreenshots" class="voice-screenshots" aria-live="polite"></div>\n              '+old)
        text=once(text,'./app.js?v=20260914-photos-v1','./app.js?v=20260914-screenshots-v1')
        text=once(text,'</body>','  <link rel="stylesheet" href="./voice-screenshots.css?v=20260914-screenshots-v1">\n  <script src="./voice-screenshots.js?v=20260914-screenshots-v1"></script>\n</body>')
    (STAGE/name).write_text(text,encoding='utf-8')
    entries.append({'file':name,'target':target,'before':hashlib.sha256(before.read_bytes()).hexdigest()})
for folder,name,dest in [('cellx-extension-api','voice_screenshots.py','/opt/cellx-extension-api/'),
                         ('cellx-extension-ui','voice-screenshots.js','/var/www/cellx-extension-ui/'),
                         ('cellx-extension-ui','voice-screenshots.css','/var/www/cellx-extension-ui/')]:
    (STAGE/name).write_bytes((ROOT/folder/name).read_bytes())
    entries.append({'file':name,'target':dest+name,'before':None})
for entry in entries: entry['after']=hashlib.sha256((STAGE/entry['file']).read_bytes()).hexdigest()
(STAGE/'manifest.json').write_text(json.dumps(entries))
for name in ['app.js','voice-screenshots.js']:subprocess.run(['node','--check',str(STAGE/name)],check=True)
remote=subprocess.check_output(SSH+['mktemp -d /tmp/cellx-screenshot-deploy-XXXXXXXX'],text=True).strip()
assert remote.startswith('/tmp/cellx-screenshot-deploy-')
for name in [e['file'] for e in entries]+['manifest.json']:
    subprocess.run(SCP+[str(STAGE/name),HOST+':'+remote+'/'+name],check=True)
subprocess.run(SCP+[str(ROOT/'scripts/install_photo_uploads.py'),HOST+':'+remote+'/install.py'],check=True)
subprocess.run(SSH+['sudo python3 '+remote+'/install.py'],check=True)
