"""Persistent daily workflow execution using the API's existing node dispatcher."""
import copy
import json
import os
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def utc_now():
    return datetime.now(timezone.utc)


def daily_settings(workflow):
    triggers = [node for node in workflow.get("nodes", []) if node.get("type") == "trigger" and node.get("action") == "cron"]
    if len(triggers) != 1:
        raise ValueError("A scheduled workflow needs exactly one cron trigger.")
    settings = triggers[0].get("integrationSettings") or {}
    expression = str(settings.get("schedule") or "").strip()
    match = re.fullmatch(r"(\d{1,2})\s+(\d{1,2})\s+\*\s+\*\s+\*", expression)
    if not match or int(match[1]) > 59 or int(match[2]) > 23:
        raise ValueError("Daily schedules use 'minute hour * * *', for example '0 6 * * *'.")
    zone = str(settings.get("timezone") or "").strip()
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Choose a valid IANA timezone, for example America/Los_Angeles.") from None
    return int(match[1]), int(match[2]), zone, str(settings.get("scheduleEnabled", "false")).lower() == "true"


def next_daily(workflow, after):
    minute, hour, zone_name, _ = daily_settings(workflow)
    zone = ZoneInfo(zone_name)
    local = after.astimezone(zone)
    for offset in range(3):
        date = local.date() + timedelta(days=offset)
        candidate = datetime(date.year, date.month, date.day, hour, minute, tzinfo=zone)
        # Spring-forward gaps move to the corresponding valid time; fall-back runs once.
        candidate = candidate.astimezone(timezone.utc)
        if candidate > after:
            return candidate
    raise ValueError("Could not calculate the next daily run.")


def ordered_nodes(workflow):
    nodes = workflow.get("nodes")
    links = workflow.get("links")
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 50 or not isinstance(links, list):
        raise ValueError("Workflow must have 1 to 50 nodes and a links array.")
    if any(not isinstance(node, dict) for node in nodes) or any(not isinstance(link, dict) for link in links):
        raise ValueError("Invalid workflow nodes or links.")
    ids = [node.get("id") for node in nodes]
    if any(not isinstance(node_id, str) or not node_id for node_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("Node IDs must be unique, nonempty strings.")
    by_id = {node["id"]: node for node in nodes}
    parents = {node_id: [] for node_id in ids}
    for link in links:
        if link.get("from") not in by_id or link.get("to") not in by_id:
            raise ValueError("Workflow contains a link to a missing node.")
        if link["from"] not in parents[link["to"]]:
            parents[link["to"]].append(link["from"])
    roots = [node_id for node_id in ids if not parents[node_id]]
    if len(roots) != 1 or by_id[roots[0]].get("type") != "trigger":
        raise ValueError("Connect every step to a single trigger.")
    ordered = []
    remaining = list(ids)
    while remaining:
        ready = next((node_id for node_id in remaining if all(p in ordered for p in parents[node_id])), None)
        if ready is None:
            raise ValueError("Scheduled workflows cannot contain cycles or disconnected steps.")
        remaining.remove(ready)
        ordered.append(ready)
    for node in nodes:
        kind = node.get("type")
        action = str(node.get("action") or "")
        settings = node.get("integrationSettings") or {}
        if not isinstance(settings, dict):
            raise ValueError("Node settings must be an object.")
        supported = kind in {"trigger", "script", "cellx-db", "log"} or (kind == "tool" and "json-transform" in action)
        if not supported:
            raise ValueError(f"{node.get('name', kind)} is not supported by the daily runner yet.")
        if kind == "cellx-db" and settings.get("operation", "query") not in {"query", "bulk_import", "insert", "upsert"}:
            raise ValueError("Scheduled database nodes support query, insert, upsert and bulk import.")
    return [by_id[node_id] for node_id in ordered], parents


def normalized_workflow(value):
    if not isinstance(value, dict):
        raise ValueError("A workflow object is required.")
    workflow = copy.deepcopy(value)
    workflow_id = str(workflow.get("id") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", workflow_id):
        raise ValueError("A valid workflow ID is required.")
    ordered_nodes(workflow)
    daily_settings(workflow)
    return {
        "id": workflow_id, "name": str(workflow.get("name") or "Workflow")[:200],
        "nodes": [{key: node[key] for key in ("id", "name", "type", "action", "integrationSettings") if key in node} for node in workflow["nodes"]],
        "links": [{"from": link["from"], "to": link["to"]} for link in workflow["links"]],
    }


def configuration_errors(workflow):
    errors = []
    for node in workflow["nodes"]:
        settings = node.get("integrationSettings") or {}
        if node.get("type") == "script":
            try:
                data = settings.get("inputJson") or "{}"
                data = json.loads(data) if isinstance(data, str) else data
                if not isinstance(data, dict):
                    raise ValueError()
            except (ValueError, TypeError):
                errors.append(f"{node.get('name')}: Input JSON must be a JSON object.")
                continue
            if not settings.get("scriptName"):
                errors.append(f"{node.get('name')}: Script Name is required.")
            if "orderdesk" in str(settings.get("scriptName", "")).lower():
                for field, key, env_key in (("orderdeskStoreId", "store_id", "ORDERDESK_STORE_ID"), ("orderdeskApiKey", "api_key", "ORDERDESK_API_KEY")):
                    value = settings.get(field) or data.get(key) or os.getenv(env_key)
                    if not value or str(value).strip() in {"***", "********"}:
                        errors.append(f"{node.get('name')}: {env_key} is not saved on the server.")
        if node.get("type") == "cellx-db" and settings.get("operation", "query") != "query":
            if settings.get("safetyMode") != "approved_write" or str(settings.get("executeWrite", "true")).lower() == "false":
                errors.append(f"{node.get('name')}: enable approved_write to run the database write.")
    return errors


class WorkflowScheduler:
    def __init__(self, path, dispatch):
        self.path = path
        self.dispatch = dispatch
        self.stop_event = threading.Event()
        self.thread = None
        self.worker_lock = threading.Lock()
        self.process_lock = None
        self.heartbeat = None
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        if os.name == "posix":
            os.chmod(path, 0o600)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, workflow TEXT NOT NULL,
                    enabled INTEGER NOT NULL, next_run TEXT, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, slot TEXT NOT NULL,
                    source TEXT NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL,
                    finished_at TEXT, UNIQUE(workflow_id, slot)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_workflow ON runs(workflow_id) WHERE status = 'running';
                CREATE TABLE IF NOT EXISTS run_steps (
                    run_id TEXT NOT NULL, node_id TEXT NOT NULL, name TEXT NOT NULL,
                    status TEXT NOT NULL, message TEXT NOT NULL, row_count INTEGER,
                    PRIMARY KEY(run_id, node_id)
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, value, now=None):
        now = now or utc_now()
        workflow = normalized_workflow(value)
        enabled = daily_settings(workflow)[3]
        errors = configuration_errors(workflow) if enabled else []
        if errors:
            raise ValueError(" ".join(errors))
        encoded = json.dumps(workflow)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT * FROM schedules WHERE id = ?", (workflow["id"],)).fetchone()
            next_run = next_daily(workflow, now).isoformat() if enabled else None
            # Saving an unchanged schedule must not postpone an already-due run.
            if previous and previous["enabled"] and enabled and daily_settings(json.loads(previous["workflow"])) == daily_settings(workflow):
                next_run = previous["next_run"]
            db.execute("""INSERT INTO schedules VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name, workflow=excluded.workflow,
                enabled=excluded.enabled, next_run=excluded.next_run, updated_at=excluded.updated_at""",
                (workflow["id"], workflow["name"], encoded, int(enabled), next_run, now.isoformat()))
        return self.status(workflow["id"])

    def status(self, workflow_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM schedules WHERE id = ?", (workflow_id,)).fetchone()
            if not row:
                return {"saved": False, "enabled": False, "runs": []}
            workflow = json.loads(row["workflow"])
            minute, hour, zone, _ = daily_settings(workflow)
            runs = []
            for run in db.execute("SELECT * FROM runs WHERE workflow_id = ? ORDER BY started_at DESC LIMIT 10", (workflow_id,)):
                record = dict(run)
                record["steps"] = [dict(step) for step in db.execute("SELECT node_id, name, status, message, row_count FROM run_steps WHERE run_id = ? ORDER BY rowid", (run["id"],))]
                runs.append(record)
        return {"saved": True, "enabled": bool(row["enabled"]), "workflowId": row["id"], "name": row["name"],
                "schedule": f"{minute} {hour} * * *", "timezone": zone, "nextRun": row["next_run"], "runs": runs}

    def health(self):
        return {"running": bool(self.thread and self.thread.is_alive()), "lastPoll": self.heartbeat, "intervalSeconds": 15}

    def claim(self, workflow_id, now, source="scheduled", workflow=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if source == "scheduled":
                row = db.execute("SELECT * FROM schedules WHERE id = ? AND enabled = 1 AND next_run <= ?", (workflow_id, now.isoformat())).fetchone()
                if not row:
                    return None
                workflow = json.loads(row["workflow"])
                slot = datetime.fromisoformat(row["next_run"]).astimezone(ZoneInfo(daily_settings(workflow)[2])).date().isoformat()
            else:
                slot = "manual:" + uuid.uuid4().hex
            run_id = uuid.uuid4().hex
            try:
                db.execute("INSERT INTO runs(id, workflow_id, slot, source, status, started_at) VALUES (?, ?, ?, ?, 'running', ?)",
                           (run_id, workflow_id, slot, source, now.isoformat()))
            except sqlite3.IntegrityError:
                # An active run blocks overlap; completed slots must never be replayed.
                if source == "scheduled" and db.execute("SELECT 1 FROM runs WHERE workflow_id=? AND slot=? AND status != 'running'", (workflow_id, slot)).fetchone():
                    db.execute("UPDATE schedules SET next_run=? WHERE id=?", (next_daily(workflow, now).isoformat(), workflow_id))
                return None
            if source == "scheduled":
                db.execute("UPDATE schedules SET next_run=? WHERE id=?", (next_daily(workflow, now).isoformat(), workflow_id))
        return run_id, workflow

    def execute(self, run_id, workflow, source):
        ordered, parents = ordered_nodes(workflow)
        outcomes = {}
        results = []
        try:
            for node in ordered:
                kind = node["type"]
                previous = [{"node": outcomes[parent]["name"], "output": outcomes[parent]["output"]} for parent in parents[node["id"]]]
                payload = {"nodeName": node.get("name", kind), "nodeType": kind, "action": node.get("action", ""),
                           "settings": node.get("integrationSettings") or {}, "previousOutputs": previous, "required": [],
                           "workflowName": workflow["name"]}
                if any(outcomes[parent]["status"] != "success" for parent in parents[node["id"]]):
                    result = {"ok": False, "status": "skipped", "message": "An upstream step failed; this step was not executed.", "output": {}}
                elif kind == "trigger":
                    result = {"ok": True, "status": "success", "message": "Workflow triggered.", "output": {"runId": run_id, "source": source}}
                elif kind == "log":
                    result = {"ok": True, "status": "success", "message": "Run recorded in scheduler history.", "output": {"runId": run_id, "source": source, "logged": True}}
                else:
                    try:
                        result, http_status = self.dispatch(payload)
                        output = result.get("output") or {}
                        failed = http_status >= 400 or result.get("ok") is False or result.get("status") in {"error", "manual"} or (isinstance(output, dict) and output.get("ok") is False)
                        result["status"] = "error" if failed else "success"
                    except Exception as exc:
                        # Avoid persisting exception strings which may contain provider secrets.
                        result = {"ok": False, "status": "error", "message": f"Node execution failed ({type(exc).__name__}).", "output": {}}
                output = result.get("output") or {}
                entry = {"nodeId": node["id"], "name": node.get("name", kind), "status": result["status"],
                         "message": result.get("message", ""), "input": result.get("input", {}), "output": output}
                outcomes[node["id"]] = entry
                results.append(entry)
                row_count = None
                if isinstance(output, dict):
                    row_count = output.get("writtenRows", output.get("row_count"))
                    if row_count is None and isinstance(output.get("rows"), list):
                        row_count = len(output["rows"])
                row_count = row_count if isinstance(row_count, int) else None
                # History stores status/counts, never API keys or customer order payloads.
                message = "Step completed." if entry["status"] == "success" else "Upstream failure." if entry["status"] == "skipped" else "Step failed. Use Test Selected to inspect provider details."
                with self.connect() as db:
                    db.execute("INSERT INTO run_steps VALUES (?, ?, ?, ?, ?, ?)", (run_id, node["id"], entry["name"], entry["status"], message, row_count))
            success = all(item["status"] == "success" for item in results)
        except Exception:
            with self.connect() as db:
                db.execute("UPDATE runs SET status='error', finished_at=? WHERE id=?", (utc_now().isoformat(), run_id))
            raise
        with self.connect() as db:
            db.execute("UPDATE runs SET status=?, finished_at=? WHERE id=?", ("success" if success else "error", utc_now().isoformat(), run_id))
        print(json.dumps({"event": "workflow.run.finished", "runId": run_id, "workflowId": workflow["id"], "source": source, "status": "success" if success else "error", "steps": len(results)}), flush=True)
        return {"ok": success, "runId": run_id, "status": "success" if success else "error", "results": results}

    def run_manual(self, value):
        workflow = normalized_workflow(value)
        errors = configuration_errors(workflow)
        if errors:
            raise ValueError(" ".join(errors))
        claim = self.claim(workflow["id"], utc_now(), "manual", workflow)
        if not claim:
            raise ValueError("This workflow is already running.")
        return self.execute(*claim, "manual")

    def tick(self, now=None):
        now = now or utc_now()
        self.heartbeat = now.isoformat()
        if not self.worker_lock.acquire(blocking=False):
            return 0
        try:
            with self.connect() as db:
                ids = [row["id"] for row in db.execute("SELECT id FROM schedules WHERE enabled=1 AND next_run <= ? ORDER BY next_run", (now.isoformat(),))]
            count = 0
            for workflow_id in ids:
                if self.stop_event.is_set():
                    break
                claim = self.claim(workflow_id, now)
                if claim:
                    self.execute(*claim, "scheduled")
                    count += 1
            return count
        finally:
            self.worker_lock.release()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        if os.name == "posix":
            import fcntl
            self.process_lock = open(self.path + ".lock", "a")
            try:
                fcntl.flock(self.process_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.process_lock.close()
                self.process_lock = None
                return
        with self.connect() as db:
            db.execute("UPDATE runs SET status='interrupted', finished_at=? WHERE status='running'", (utc_now().isoformat(),))
        self.stop_event.clear()

        def worker():
            while not self.stop_event.is_set():
                try:
                    self.tick()
                except Exception as exc:
                    print(f"workflow scheduler poll failed ({type(exc).__name__})", flush=True)
                self.stop_event.wait(15)

        self.thread = threading.Thread(target=worker, name="workflow-daily-scheduler", daemon=True)
        self.thread.start()
