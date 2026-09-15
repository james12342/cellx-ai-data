"""Atomic photo-feature deployment with live hash checks and service rollback."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import time
from urllib.request import urlopen

stage = Path(__file__).parent
entries = json.loads((stage / "manifest.json").read_text())
for e in entries:
    target = Path(e["target"])
    assert target.parent in {Path("/opt/cellx-extension-api"), Path("/var/www/cellx-extension-ui")}
    assert (hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None) == e["before"], "Live file changed"
    assert hashlib.sha256((stage / e["file"]).read_bytes()).hexdigest() == e["after"]
    if target.suffix == ".py": compile((stage / e["file"]).read_text(), str(target), "exec")
pid = subprocess.check_output(["systemctl", "show", "cellx-extension-api", "-p", "MainPID", "--value"], text=True).strip()
env = dict(p.decode().split("=", 1) for p in Path("/proc/" + pid + "/environ").read_bytes().split(b"\0") if b"=" in p)
schedule = Path(env.get("WORKFLOW_SCHEDULE_DB", "/opt/cellx-extension-api/workflow-schedules.sqlite3"))
if schedule.exists():
    with sqlite3.connect(schedule.as_uri()+"?mode=ro", uri=True) as db:
        assert db.execute("SELECT count(*) FROM runs WHERE status='running'").fetchone()[0] == 0, "Workflow running; retry later"
        for (date,) in db.execute("SELECT next_run FROM schedules WHERE enabled=1 AND next_run IS NOT NULL"):
            assert datetime.fromisoformat(date.replace("Z", "+00:00")) > datetime.now(timezone.utc)+timedelta(minutes=2), "Schedule imminent"
backup = Path(tempfile.mkdtemp(prefix="cellx-before-photos-"))
for e in entries:
    if Path(e["target"]).exists(): shutil.copy2(e["target"], backup/e["file"])

def restart():
    subprocess.run(["systemctl", "restart", "cellx-extension-api"], check=True, timeout=30)
    for _ in range(30):
        try:
            health = json.load(urlopen("http://127.0.0.1:3001/health", timeout=2))
            if health.get("ok") and health.get("scheduler", {}).get("running"): return
        except Exception: pass
        time.sleep(.5)
    raise RuntimeError("Health check failed")

try:
    for e in sorted(entries, key=lambda item:item["file"].endswith(".html")):
        target = Path(e["target"])
        temporary = target.with_name(target.name+".photos-stage")
        shutil.copyfile(stage/e["file"], temporary)
        os.chmod(temporary, 0o644)
        os.replace(temporary,target)
    restart()
except Exception:
    for e in entries:
        old=backup/e["file"]
        if old.exists(): shutil.copy2(old,e["target"])
        else: Path(e["target"]).unlink(missing_ok=True)
    restart()
    raise
print("Photo upload deployed; service and scheduler healthy. Backup:", backup)
