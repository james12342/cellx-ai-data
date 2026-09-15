"""Stage only the photo feature against live files; preserve unrelated local work."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "outputs/photo-upload-deploy"
STAGE.mkdir(parents=True, exist_ok=True)
HOST = "ubuntu@44.240.97.37"
KEY = "C:/Users/hibre/Downloads/LightsailDefaultKey-us-west-2.pem"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-i", KEY, HOST]
SCP = ["scp", "-o", "BatchMode=yes", "-i", KEY]


def once(text, old, new):
    assert text.count(old) == 1, "Live anchor differs: " + old[:80]
    return text.replace(old, new)


targets = {"server.py": "/opt/cellx-extension-api/server.py",
           "app.js": "/var/www/cellx-extension-ui/app.js",
           "index.html": "/var/www/cellx-extension-ui/index.html"}
manifest = []
for name, target in targets.items():
    before = STAGE / (name + ".before")
    subprocess.run(SCP + [HOST + ":" + target, str(before)], check=True)
    old = before.read_text(encoding="utf-8")
    text = old
    if name == "server.py":
        local = (ROOT / "cellx-extension-api/server.py").read_text(encoding="utf-8")
        tree = ast.parse(local)
        handler = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Handler")
        method = next(n for n in handler.body if isinstance(n, ast.FunctionDef) and n.name == "serve_photo_upload")
        segment = "\n".join(local.splitlines()[method.lineno-1:method.end_lineno]) + "\n\n"
        anchor = "class Handler(BaseHTTPRequestHandler):\n"
        text = once(text, anchor, anchor + segment)
        for anchor, check in [
            ('    def do_PUT(self):\n', 'normalize_api_path(urlparse(self.path).path)'),
            ('    def do_GET(self):\n', 'normalize_api_path(urlparse(self.path).path)'),
            ('    def do_POST(self):\n        path = normalize_api_path(urlparse(self.path).path)\n', 'path'),
        ]:
            text = once(text, anchor, anchor + f'        if {check}.startswith("/photo-uploads"):\n            return self.serve_photo_upload()\n')
        ast.parse(text)
    elif name == "app.js":
        anchor = 'async function testNodeIntegration(node, execute = false) {\n'
        text = once(text, anchor, anchor + '  if (window.WorkflowPhotos?.isNode(node)) {\n    return window.WorkflowPhotos.test(node);\n  }\n')
        text = once(text, 'function render() {\n', 'function render() {\n  window.WorkflowPhotos?.render();\n')
        anchor = '    return {\n      ...node,\n      integrationSettings,\n    };'
        text = once(text, anchor, '    delete integrationSettings.photoFilesJson;\n    if (node.integrationSettings?.photoFilesJson) integrationSettings.photoFilesJson = node.integrationSettings.photoFilesJson;\n    return { ...node, integrationSettings };')
    else:
        old_button = '<button id="clearBtn" type="button" data-i18n="Clear">Clear</button>'
        text = once(text, old_button, '<div class="canvas-head-actions"><button id="uploadPhotosBtn" type="button" hidden>Upload Photos</button>' + old_button + '</div>')
        text = once(text, '<script src="./app.js?v=20260914-i18n-v1"></script>',
                    '<link rel="stylesheet" href="./workflow-photos.css?v=20260914-photos-v1">\n  <script src="./app.js?v=20260914-photos-v1"></script>\n  <script src="./workflow-photos.js?v=20260914-photos-v1"></script>')
    (STAGE / name).write_text(text, encoding="utf-8")
    manifest.append({"target": target, "file": name, "before": hashlib.sha256(before.read_bytes()).hexdigest()})

for folder, name, dest in [("cellx-extension-api", "photo_uploads.py", "/opt/cellx-extension-api/"),
                           ("cellx-extension-ui", "workflow-photos.js", "/var/www/cellx-extension-ui/"),
                           ("cellx-extension-ui", "workflow-photos.css", "/var/www/cellx-extension-ui/")]:
    (STAGE / name).write_bytes((ROOT / folder / name).read_bytes())
    manifest.append({"target": dest + name, "file": name, "before": None})
for entry in manifest:
    entry["after"] = hashlib.sha256((STAGE / entry["file"]).read_bytes()).hexdigest()
(STAGE / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
for name in ["app.js", "workflow-photos.js"]:
    subprocess.run(["node", "--check", str(STAGE / name)], check=True)
remote = subprocess.check_output(SSH + ["mktemp -d /tmp/cellx-photo-deploy-XXXXXXXX"], text=True).strip()
assert remote.startswith("/tmp/cellx-photo-deploy-") and " " not in remote
for name in [e["file"] for e in manifest] + ["manifest.json"]:
    subprocess.run(SCP + [str(STAGE / name), HOST + ":" + remote + "/" + name], check=True)
subprocess.run(SCP + [str(ROOT / "scripts/install_photo_uploads.py"), HOST + ":" + remote + "/install.py"], check=True)
subprocess.run(SSH + ["sudo python3 " + remote + "/install.py"], check=True)
