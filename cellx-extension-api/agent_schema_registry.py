"""Admin-only schema draft registry. No business database access or DDL executor."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
import uuid

from agent_schema_planner import delete_impact, digest, physical_table_name, preview_schema, resource_id, validate_manifest


class RegistryError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def now():
    return datetime.now(timezone.utc).isoformat()


def only(body, keys):
    if not isinstance(body, dict) or set(body) - set(keys):
        raise RegistryError(400, "unsupported_request_fields")


class AgentSchemaRegistry:
    def __init__(self, path, runtime_guard=None):
        self.path = str(path)
        self.runtime_guard = runtime_guard or (lambda agent_id: True)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        if os.name == "posix":
            os.chmod(self.path, 0o600)
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            application_id = db.execute("PRAGMA application_id").fetchone()[0]
            occupied = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1").fetchone()
            if application_id != 1128354642 and (application_id != 0 or occupied or version != 0):
                raise RegistryError(503, "not_an_agent_schema_registry")
            if version not in (0, 1):
                raise RegistryError(503, "unsupported_registry_version")
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0,
                    created_by TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agents (
                    tenant_id TEXT NOT NULL REFERENCES tenants(id), id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('active','deleted')),
                    version INTEGER NOT NULL DEFAULT 0, manifest TEXT,
                    created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
                    PRIMARY KEY(tenant_id,id)
                );
                CREATE TABLE IF NOT EXISTS table_registry (
                    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    entity_key TEXT NOT NULL, scope TEXT NOT NULL CHECK(scope IN ('company','agent')),
                    scope_key TEXT NOT NULL, physical_name TEXT NOT NULL UNIQUE,
                    creator_agent_id TEXT NOT NULL, owner_agent_id TEXT,
                    fields TEXT NOT NULL, field_creators TEXT NOT NULL, schema_hash TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'planned' CHECK(state='planned'),
                    usage_status TEXT NOT NULL DEFAULT 'planned_in_use',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id,scope_key,entity_key), UNIQUE(tenant_id,id)
                );
                CREATE TABLE IF NOT EXISTS table_use (
                    tenant_id TEXT NOT NULL, agent_id TEXT NOT NULL, table_id TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('active','retained')), fields TEXT NOT NULL,
                    relationships TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id,agent_id,table_id),
                    FOREIGN KEY(tenant_id,agent_id) REFERENCES agents(tenant_id,id),
                    FOREIGN KEY(tenant_id,table_id) REFERENCES table_registry(tenant_id,id)
                );
                CREATE TABLE IF NOT EXISTS agent_revisions (
                    tenant_id TEXT NOT NULL, agent_id TEXT NOT NULL, version INTEGER NOT NULL,
                    manifest TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id,agent_id,version),
                    FOREIGN KEY(tenant_id,agent_id) REFERENCES agents(tenant_id,id)
                );
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, agent_id TEXT NOT NULL,
                    kind TEXT NOT NULL, revision INTEGER NOT NULL, agent_version INTEGER NOT NULL,
                    plan_hash TEXT NOT NULL, result TEXT NOT NULL, expires_at REAL NOT NULL,
                    completed_result TEXT, created_at TEXT NOT NULL,
                    FOREIGN KEY(tenant_id,agent_id) REFERENCES agents(tenant_id,id)
                );
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL, agent_id TEXT,
                    actor TEXT NOT NULL, operation TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
                );
                PRAGMA user_version=1;
                PRAGMA application_id=1128354642;
                COMMIT;
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def agent(self, db, tenant_id, agent_id, active=True):
        resource_id(tenant_id)
        resource_id(agent_id)
        row = db.execute("SELECT * FROM agents WHERE tenant_id=? AND id=?", (tenant_id, agent_id)).fetchone()
        if row is None:
            raise RegistryError(404, "agent_not_found")
        if active and row["state"] != "active":
            raise RegistryError(409, "agent_deleted")
        return row

    def audit(self, db, tenant, agent, operation, detail):
        db.execute("INSERT INTO audit(tenant_id,agent_id,actor,operation,detail,created_at) VALUES (?,?,?,?,?,?)",
                   (tenant, agent, "workflow-admin", operation, encoded(detail), now()))

    def snapshot(self, db, tenant):
        row = db.execute("SELECT revision FROM tenants WHERE id=?", (tenant,)).fetchone()
        if row is None:
            raise RegistryError(404, "tenant_not_found")
        tables = []
        for table in db.execute("SELECT * FROM table_registry WHERE tenant_id=? ORDER BY entity_key,id", (tenant,)):
            uses = list(db.execute("SELECT * FROM table_use WHERE tenant_id=? AND table_id=?", (tenant, table["id"])))
            consumers = {}
            relations = []
            for use in uses:
                for field in json.loads(use["fields"]):
                    consumers.setdefault(field, []).append(use["agent_id"])
                relations.extend(json.loads(use["relationships"]))
            tables.append({"id": table["id"], "tenant_id": tenant, "entity_key": table["entity_key"],
                           "scope": table["scope"], "physical_name": table["physical_name"],
                           "owner_agent_id": table["owner_agent_id"], "creator_agent_id": table["creator_agent_id"],
                           "managed": True, "state": "planned", "physical_exists": None,
                           "usage_status": table["usage_status"],
                           "fields": json.loads(table["fields"]), "field_consumers": consumers,
                           "field_creators": json.loads(table["field_creators"]), "relationships": relations,
                           "references": [u["agent_id"] for u in uses],
                           "active_references": [u["agent_id"] for u in uses if u["state"] == "active"],
                           "dependency_inventory_complete": False, "retention_hold": None, "row_count": None})
        agents = {a["id"]: {"state": a["state"], "version": a["version"], "history_count": None}
                  for a in db.execute("SELECT id,state,version FROM agents WHERE tenant_id=?", (tenant,))}
        return {"tenant_id": tenant, "revision": row["revision"], "agents": agents, "tables": tables,
                "occupied_physical_names": [r[0] for r in db.execute("SELECT physical_name FROM table_registry")]}

    def refresh_usage(self, db, tenant):
        db.execute("""UPDATE table_registry SET usage_status=CASE WHEN EXISTS (
            SELECT 1 FROM table_use u WHERE u.tenant_id=table_registry.tenant_id
            AND u.table_id=table_registry.id AND u.state='active'
        ) THEN 'planned_in_use' ELSE 'unused_planned' END WHERE tenant_id=?""", (tenant,))

    def save_manifest(self, db, body):
        only(body, {"tenant_id", "agent_id", "expected_version", "manifest"})
        tenant, agent_id = body["tenant_id"], body["agent_id"]
        agent = self.agent(db, tenant, agent_id)
        if type(body.get("expected_version")) is not int or body["expected_version"] != agent["version"]:
            raise RegistryError(409, "stale_agent_version")
        manifest = validate_manifest(body["manifest"])
        if (manifest["tenant_id"], manifest["agent_id"]) != (tenant, agent_id):
            raise RegistryError(403, "manifest_scope_mismatch")
        proposal = preview_schema(tenant, manifest, self.snapshot(db, tenant))
        if proposal["blockers"]:
            raise RegistryError(409, "schema_conflict")
        db.execute("UPDATE table_use SET state='retained',updated_at=? WHERE tenant_id=? AND agent_id=?", (now(), tenant, agent_id))
        for table in manifest["tables"]:
            key = "company" if table["scope"] == "company" else agent_id
            existing = db.execute("SELECT * FROM table_registry WHERE tenant_id=? AND scope_key=? AND entity_key=?",
                                  (tenant, key, table["entity_key"])).fetchone()
            fields = {f["name"]: f for f in json.loads(existing["fields"])} if existing else {}
            creators = json.loads(existing["field_creators"]) if existing else {}
            for field in table["fields"]:
                fields[field["name"]] = field
                creators.setdefault(field["name"], agent_id)
            fields = [fields[k] for k in sorted(fields)]
            table_id = existing["id"] if existing else "table_" + uuid.uuid4().hex
            if existing:
                db.execute("UPDATE table_registry SET fields=?,field_creators=?,schema_hash=?,updated_at=? WHERE id=?",
                           (encoded(fields), encoded(creators), digest(fields), now(), table_id))
            else:
                db.execute("""INSERT INTO table_registry
                    (id,tenant_id,entity_key,scope,scope_key,physical_name,creator_agent_id,owner_agent_id,
                     fields,field_creators,schema_hash,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (table_id, tenant, table["entity_key"], table["scope"], key,
                            physical_table_name(tenant, table["scope"], table["entity_key"], agent_id), agent_id,
                            agent_id if table["scope"] == "agent" else None, encoded(fields), encoded(creators), digest(fields), now(), now()))
            relations = [r for r in manifest.get("relationships", []) if r["source_table"] == table["entity_key"]]
            db.execute("""INSERT INTO table_use VALUES (?,?,?,'active',?,?,?)
                ON CONFLICT(tenant_id,agent_id,table_id) DO UPDATE SET state='active',fields=excluded.fields,
                relationships=excluded.relationships,updated_at=excluded.updated_at""",
                       (tenant, agent_id, table_id, encoded([f["name"] for f in table["fields"]]), encoded(relations), now()))
        version = agent["version"] + 1
        db.execute("UPDATE agents SET manifest=?,version=?,updated_at=? WHERE tenant_id=? AND id=?",
                   (encoded(manifest), version, now(), tenant, agent_id))
        db.execute("INSERT INTO agent_revisions VALUES (?,?,?,?,?)", (tenant, agent_id, version, encoded(manifest), now()))
        db.execute("UPDATE tenants SET revision=revision+1 WHERE id=?", (tenant,))
        self.refresh_usage(db, tenant)
        self.audit(db, tenant, agent_id, "save_schema_draft", {"version": version, "manifest_hash": digest(manifest)})
        return {"version": version, "state": "planned", "business_ddl_executed": False,
                "tables": self.snapshot(db, tenant)["tables"]}

    def plan(self, db, body, kind):
        only(body, {"tenant_id", "agent_id"})
        tenant, agent_id = body["tenant_id"], body["agent_id"]
        agent = self.agent(db, tenant, agent_id)
        snapshot = self.snapshot(db, tenant)
        if kind == "schema":
            if not agent["manifest"]:
                raise RegistryError(409, "manifest_not_saved")
            result = preview_schema(tenant, json.loads(agent["manifest"]), snapshot)
        else:
            result = delete_impact(tenant, agent_id, snapshot)
            result["schedule_action"] = "not_managed_by_registry"
            result["lifecycle_scope"] = "registry_schema_draft_only"
            for table in result["tables"]:
                table["physical_exists"] = None
                table["state"] = "planned"
        result["physical_inventory_verified"] = False
        plan_id = uuid.uuid4().hex
        plan_hash = digest([tenant, agent_id, kind, snapshot["revision"], agent["version"], result])
        expires = time.time() + 900
        db.execute("INSERT INTO plans VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (plan_id, tenant, agent_id, kind, snapshot["revision"], agent["version"], plan_hash, encoded(result), expires, None, now()))
        return {**result, "plan_id": plan_id, "plan_hash": plan_hash, "expires_at": expires}

    def use_plan(self, db, body, kind):
        tenant, agent_id = body["tenant_id"], body["agent_id"]
        agent = self.agent(db, tenant, agent_id, active=False)
        plan = db.execute("SELECT * FROM plans WHERE id=? AND tenant_id=? AND agent_id=? AND kind=?",
                          (body["plan_id"], tenant, agent_id, kind)).fetchone()
        if not plan or not secrets.compare_digest(str(body.get("plan_hash", "")), plan["plan_hash"]):
            raise RegistryError(409, "invalid_plan")
        if kind == "delete" and plan["completed_result"]:
            return json.loads(plan["completed_result"])
        revision = db.execute("SELECT revision FROM tenants WHERE id=?", (tenant,)).fetchone()[0]
        if plan["expires_at"] <= time.time() or plan["revision"] != revision or plan["agent_version"] != agent["version"]:
            raise RegistryError(409, "stale_or_expired_plan")
        if agent["state"] != "active":
            raise RegistryError(409, "agent_deleted")
        result = json.loads(plan["result"])
        if kind == "schema":
            self.audit(db, tenant, agent_id, "apply_dry_run", {"plan_id": plan["id"]})
            return {**result, "mode": "dry_run", "executed": False, "business_ddl_executed": False,
                    "reason": "physical_schema_apply_not_implemented"}
        # Until execution/lease integration exists, refuse lifecycle actions on any runtime-bound ID.
        if self.runtime_guard(agent_id):
            raise RegistryError(409, "runtime_binding_requires_lifecycle_bridge")
        db.execute("UPDATE agents SET state='deleted',version=version+1,deleted_at=?,updated_at=? WHERE tenant_id=? AND id=?",
                   (now(), now(), tenant, agent_id))
        db.execute("UPDATE table_use SET state='retained',updated_at=? WHERE tenant_id=? AND agent_id=?", (now(), tenant, agent_id))
        db.execute("UPDATE tenants SET revision=revision+1 WHERE id=?", (tenant,))
        self.refresh_usage(db, tenant)
        for table in result["tables"]:
            table["registry_usage_status"] = db.execute("SELECT usage_status FROM table_registry WHERE tenant_id=? AND id=?",
                                                       (tenant, table["table_id"])).fetchone()[0]
        result.update({"mode": "registry_soft_delete", "registry_updated": True, "state": "deleted",
                       "business_ddl_executed": False, "data_preserved": True, "can_execute": False})
        self.audit(db, tenant, agent_id, "soft_delete_registry_agent", {"plan_id": plan["id"], "tables_retained": len(result["tables"])})
        db.execute("UPDATE plans SET completed_result=? WHERE id=?", (encoded(result), plan["id"]))
        return result

    def dispatch(self, operation, body):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if operation == "status":
                return {"storage": "sqlite", "registry_version": 1, "admin_only": True,
                        "preview_enabled": True, "real_apply_enabled": False, "runtime_integrated": False}
            if operation == "tenants/create":
                only(body, {"tenant_id", "name"})
                tenant = resource_id(body["tenant_id"])
                name = str(body.get("name") or tenant)[:200]
                db.execute("INSERT INTO tenants(id,name,created_by,created_at) VALUES (?,?,?,?)", (tenant, name, "workflow-admin", now()))
                self.audit(db, tenant, None, "create_tenant", {})
                return {"tenant_id": tenant, "membership_mode": "operator_managed_not_customer_verified"}
            if operation == "agents/create":
                only(body, {"tenant_id", "name"})
                tenant = resource_id(body["tenant_id"])
                if not db.execute("SELECT 1 FROM tenants WHERE id=?", (tenant,)).fetchone():
                    raise RegistryError(404, "tenant_not_found")
                agent = "asr_" + uuid.uuid4().hex
                name = str(body.get("name") or "Schema draft")[:200]
                db.execute("INSERT INTO agents(tenant_id,id,name,state,created_by,created_at,updated_at) VALUES (?,?,?,'active',?,?,?)",
                           (tenant, agent, name, "workflow-admin", now(), now()))
                db.execute("UPDATE tenants SET revision=revision+1 WHERE id=?", (tenant,))
                self.audit(db, tenant, agent, "create_schema_agent", {})
                return {"agent_id": agent, "tenant_id": tenant, "version": 0, "runtime_integrated": False}
            if operation == "manifest/save":
                return self.save_manifest(db, body)
            if operation == "schema/preview":
                return self.plan(db, body, "schema")
            if operation == "delete-impact":
                return self.plan(db, body, "delete")
            if operation == "schema/apply":
                only(body, {"tenant_id", "agent_id", "plan_id", "plan_hash", "dry_run"})
                if body.get("dry_run") is not True:
                    raise RegistryError(501, "real_schema_apply_disabled")
                return self.use_plan(db, body, "schema")
            if operation == "delete":
                only(body, {"tenant_id", "agent_id", "plan_id", "plan_hash", "mode"})
                if body.get("mode", "keep_data") != "keep_data":
                    raise RegistryError(400, "agent_delete_must_keep_data")
                return self.use_plan(db, body, "delete")
            raise RegistryError(404, "not_found")


def handle_registry_request(operation, headers, body, *, enabled, admin_token, factory):
    # No customer-supplied email, role, tenant claim or token in JSON/query is trusted.
    if not enabled:
        return {"ok": False, "code": "agent_schema_feature_disabled"}, 503
    if not admin_token:
        return {"ok": False, "code": "admin_auth_not_configured"}, 503
    supplied = headers.get("X-Workflow-Admin-Token", "")
    if not supplied or not secrets.compare_digest(str(supplied).encode(), str(admin_token).encode()):
        return {"ok": False, "code": "admin_auth_required"}, 401
    try:
        if not isinstance(body, dict):
            raise RegistryError(400, "object_required")
        return {"ok": True, **factory().dispatch(operation, body)}, 200
    except RegistryError as exc:
        return {"ok": False, "code": exc.code}, exc.status
    except sqlite3.IntegrityError:
        return {"ok": False, "code": "registry_conflict"}, 409
    except (KeyError, ValueError, TypeError, AttributeError):
        return {"ok": False, "code": "invalid_schema_request"}, 400
    except Exception:
        return {"ok": False, "code": "registry_unavailable"}, 503
