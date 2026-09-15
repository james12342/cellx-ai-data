"""Print only presence of scheduler credentials in the running API environment."""
import json
import pathlib
import subprocess

pid = subprocess.check_output(
    ["systemctl", "show", "cellx-extension-api", "--property=MainPID", "--value"], text=True
).strip()
environment = dict(part.split(b"=", 1) for part in pathlib.Path(f"/proc/{pid}/environ").read_bytes().split(b"\0") if b"=" in part)
print(json.dumps({key: bool(environment.get(key.encode())) for key in (
    "ORDERDESK_STORE_ID", "ORDERDESK_API_KEY", "DB_USER", "DB_PASSWORD",
    "WORKFLOW_MANAGEMENT_TOKEN", "MARKETPLACE_ADMIN_TOKEN",
)}))
