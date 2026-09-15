"""Run on host: test private upload without printing credentials or photo data."""
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

pid = subprocess.check_output(["systemctl", "show", "cellx-extension-api", "-p", "MainPID", "--value"], text=True).strip()
env = dict(p.decode().split("=", 1) for p in Path("/proc/"+pid+"/environ").read_bytes().split(b"\0") if b"=" in p)
token = env.get("WORKFLOW_MANAGEMENT_TOKEN") or env.get("MARKETPLACE_ADMIN_TOKEN")
assert token, "Upload admin token missing"
base = "http://127.0.0.1:3001/ext-api"

def request(path, method="GET", payload=None, auth=True):
    headers={"Content-Type":"application/json", "Origin":"https://app.cellaidata.com"}
    if auth: headers["X-Workflow-Admin-Token"]=token
    req=Request(base+path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers, method=method)
    try:
        with urlopen(req,timeout=15) as reply: return reply.status,json.load(reply)
    except HTTPError as error: return error.code,json.load(error)

assert request("/photo-uploads", "POST", {}, False)[0] == 401
assert request("/photo-uploads", "POST", {"data":"invalid"})[0] == 400
png="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6pYkAAAAASUVORK5CYII="
status,body=request("/photo-uploads", "POST", {"name":"codex-upload-smoke.png", "data":png})
assert status == 201, body.get("message", "Upload failed")
path="/photo-uploads/"+body["file"]["id"]
try:
    assert request(path,auth=False)[0] == 401
    status,body=request(path)
    assert status == 200 and body["data"] == png
finally:
    assert request(path,"DELETE")[0] == 200
assert request(path)[0] == 404
print("Live photo API: upload, private read, byte roundtrip, delete, missing file and auth checks passed. Test photo removed.")
