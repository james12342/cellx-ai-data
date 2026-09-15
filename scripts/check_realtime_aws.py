"""Run on the existing server; print readiness only, never credentials."""
import json
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen
from urllib.error import HTTPError

pid = subprocess.check_output(["systemctl", "show", "--property", "MainPID", "--value", "cellx-extension-api"], text=True).strip()
environment = dict(item.split("=", 1) for item in Path(f"/proc/{pid}/environ").read_text().split("\0") if "=" in item)
port = environment.get("PORT", "3001")
token = environment.get("WORKFLOW_MANAGEMENT_TOKEN") or environment.get("MARKETPLACE_ADMIN_TOKEN", "")


def post(route, payload):
    request = Request(f"http://127.0.0.1:{port}/ext-api/ai/{route}", data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json", "X-Workflow-Admin-Token": token}, method="POST")
    try:
        with urlopen(request, timeout=90) as handle:
            body = json.load(handle)
        return body
    except HTTPError as error:
        data = json.load(error)
        print(json.dumps({"check": route, "status": error.code, "message": data.get("message")}))
        raise SystemExit(1)


session = post("realtime-session", {})
print(json.dumps({"check": "realtime-session", "ok": session.get("ok"), "has_ephemeral_credential": bool(session.get("value"))}))
draft = post("workflow-builder", {"prompt": "Create a design named Voice Connection Test with two nodes: Daily Schedule trigger with action cron, linked to Write Workflow Log with type log and action cx_workflow_log. Do not execute anything."})
template = draft.get("template", {})
print(json.dumps({"check": "workflow-builder", "ok": draft.get("ok"), "nodes": len(template.get("nodes", [])), "links": len(template.get("links", []))}))
if not session.get("ok") or not draft.get("ok"):
    raise SystemExit(1)
