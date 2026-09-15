"""Offline, read-only lifecycle planning. Never connects to MySQL or emits SQL."""

import copy
import hashlib
import json
import re


TYPES = {"uuid", "string", "text", "integer", "decimal", "boolean", "datetime", "json"}


def resource_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", value):
        raise ValueError("A valid opaque resource ID is required.")
    return value


def allowed_keys(value, keys):
    if not isinstance(value, dict) or set(value) - set(keys):
        raise ValueError("Unsupported manifest attributes.")


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", value):
        raise ValueError("Identifiers must be lowercase names, at most 48 characters.")
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def physical_table_name(tenant_id, scope, entity_key, agent_id):
    resource_id(tenant_id)
    resource_id(agent_id)
    identifier(entity_key)
    if scope not in {"company", "agent"}:
        raise ValueError("Invalid table scope.")
    suffix = digest([tenant_id, scope, entity_key, agent_id if scope == "agent" else None])[:24]
    # MySQL identifiers are limited to 64 characters; hash the untruncated key.
    return f"agent_{entity_key[:33]}_{suffix}"


def validate_manifest(manifest):
    manifest = copy.deepcopy(manifest)
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ValueError("Manifest version 1 is required.")
    allowed_keys(manifest, {"version", "agent_id", "tenant_id", "tables", "relationships"})
    resource_id(manifest.get("agent_id"))
    resource_id(manifest.get("tenant_id"))
    tables = manifest.get("tables")
    if not isinstance(tables, list) or not 1 <= len(tables) <= 20:
        raise ValueError("Specify 1 to 20 tables.")
    seen = set()
    for table in tables:
        if not isinstance(table, dict):
            raise ValueError("Table must be an object.")
        allowed_keys(table, {"entity_key", "scope", "fields"})
        key = identifier(table.get("entity_key"))
        if key in seen:
            raise ValueError("Duplicate entity key.")
        seen.add(key)
        if table.get("scope") not in {"company", "agent"}:
            raise ValueError("Scope must be company or agent.")
        fields = table.get("fields")
        if not isinstance(fields, list) or not 1 <= len(fields) <= 100:
            raise ValueError("Specify 1 to 100 fields per table.")
        names = set()
        for field in fields:
            if not isinstance(field, dict):
                raise ValueError("Field must be an object.")
            allowed_keys(field, {"name", "type", "nullable"})
            name = identifier(field.get("name"))
            if name in names or field.get("type") not in TYPES or type(field.get("nullable")) is not bool:
                raise ValueError("Invalid or duplicate field definition.")
            names.add(name)
        primary = next((f for f in fields if f["name"] == "id"), None)
        if primary != {"name": "id", "type": "uuid", "nullable": False}:
            raise ValueError("Every table requires a non-null UUID id.")
    relationships = manifest.get("relationships", [])
    if not isinstance(relationships, list) or len(relationships) > 100:
        raise ValueError("Invalid relationship list.")
    by_key = {table["entity_key"]: table for table in tables}
    rel_keys = set()
    for rel in relationships:
        if not isinstance(rel, dict):
            raise ValueError("Relationship must be an object.")
        allowed_keys(rel, {"key", "source_table", "source_field", "target_table", "target_field", "on_delete"})
        key = identifier(rel.get("key"))
        if key in rel_keys or rel.get("on_delete") != "restrict":
            raise ValueError("Relationships must be unique and use restrict.")
        rel_keys.add(key)
        source = by_key.get(rel.get("source_table"))
        target = by_key.get(rel.get("target_table"))
        if source is None or target is None or rel.get("target_field") != "id":
            raise ValueError("Relationship must target a manifest table UUID id.")
        field = next((f for f in source["fields"] if f["name"] == rel.get("source_field")), None)
        if field is None or field["type"] != "uuid":
            raise ValueError("Relationship source must be a UUID field.")
    return manifest


def scoped_snapshot(tenant_id, snapshot):
    """The future repository supplies this inventory; never accept it from HTTP clients."""
    if snapshot.get("tenant_id") != tenant_id:
        raise PermissionError("Tenant inventory mismatch.")
    tables = snapshot.get("tables", [])
    if any(t.get("tenant_id") != tenant_id for t in tables):
        raise PermissionError("Mixed tenant inventory is forbidden.")
    return tables


def preview_schema(tenant_id, manifest, snapshot):
    manifest = validate_manifest(manifest)
    if manifest["tenant_id"] != tenant_id:
        raise PermissionError("Manifest tenant mismatch.")
    inventory = scoped_snapshot(tenant_id, snapshot)
    actions, blockers = [], []
    agent = manifest["agent_id"]
    for desired in manifest["tables"]:
        key = desired["entity_key"]
        candidates = [t for t in inventory if t["entity_key"] == key and
                      t["scope"] == desired["scope"] and
                      (t["scope"] == "company" or t.get("owner_agent_id") == agent)]
        if len(candidates) > 1:
            blockers.append({"entity_key": key, "code": "ambiguous_registry_match"})
            continue
        if not candidates:
            physical_name = physical_table_name(tenant_id, desired["scope"], key, agent)
            occupied = set(snapshot.get("occupied_physical_names", []))
            occupied.update(t.get("physical_name") for t in inventory)
            if physical_name in occupied:
                blockers.append({"entity_key": key, "code": "physical_name_collision"})
                continue
            actions.append({"action": "propose_create_table", "entity_key": key,
                            "physical_name": physical_name, "scope": desired["scope"],
                            "fields": desired["fields"]})
            continue
        existing = candidates[0]
        if existing.get("state") not in {"active", "planned"} or existing.get("managed") is not True:
            blockers.append({"entity_key": key, "code": "adoption_or_recovery_required"})
            continue
        actions.append({"action": "reuse_planned_table" if existing["state"] == "planned" else "reuse_table",
                        "entity_key": key, "table_id": existing["id"]})
        current = {field["name"]: field for field in existing["fields"]}
        for field in desired["fields"]:
            previous = current.get(field["name"])
            if previous is None:
                if field["nullable"]:
                    actions.append({"action": "propose_add_nullable_field", "table_id": existing["id"], "field": field})
                else:
                    blockers.append({"entity_key": key, "field": field["name"], "code": "backfill_review_required"})
            elif previous != field:
                blockers.append({"entity_key": key, "field": field["name"], "code": "incompatible_field"})
        if agent not in existing.get("references", []):
            actions.append({"action": "link_agent", "table_id": existing["id"], "agent_id": agent})
    # Relationship proposals remain explicit review items, not executable constraints.
    for relation in manifest.get("relationships", []):
        actions.append({"action": "review_relationship", "relationship": relation})
    return {"mode": "preview_only", "can_apply": False, "manifest_hash": digest(manifest),
            "inventory_revision": snapshot.get("revision"), "actions": actions, "blockers": blockers,
            "warnings": ["Unregistered physical tables are not auto-adopted.",
                         "Physical schema drift, indexes and foreign keys require an authoritative database inventory."]}


def delete_impact(tenant_id, agent_id, snapshot):
    resource_id(agent_id)
    inventory = scoped_snapshot(tenant_id, snapshot)
    if agent_id not in snapshot.get("agents", {}):
        raise ValueError("Agent is not registered in this tenant.")
    output = []
    for table in inventory:
        if agent_id not in table.get("references", []) and table.get("owner_agent_id") != agent_id:
            continue
        others = sorted(set(table.get("references", [])) - {agent_id})
        notes = []
        if others:
            notes.append("referenced_by_other_agents")
        if table.get("managed") is not True or table.get("state") != "active":
            notes.append("unmanaged_or_not_active")
        if table.get("dependency_inventory_complete") is not True:
            notes.append("dependency_inventory_incomplete")
        if table.get("dependents"):
            notes.append("inbound_dependencies")
        if table.get("retention_hold") is not False:
            notes.append("retention_hold_or_unknown")
        usage = "retained_in_use" if others or table.get("dependents") else (
            "retained_review_required" if notes else "unused_orphaned")
        output.append({"table_id": table["id"], "entity_key": table["entity_key"],
                       "physical_name": table.get("physical_name"),
                       "scope": table["scope"], "default_action": "retain_table_unlink_agent",
                       "creator_agent_id": table.get("creator_agent_id"),
                       "owner_agent_id": table.get("owner_agent_id"),
                       "other_agents": others, "fields": table.get("fields", []),
                       "field_consumers": table.get("field_consumers", {}),
                       "relationships": table.get("relationships", []),
                       "relationship_consumers": table.get("relationship_consumers", {}),
                       "row_count": table.get("row_count"), "dependents": table.get("dependents", []),
                       "data_preserved": True, "usage_after_unlink": usage, "retention_notes": notes})
    return {"mode": "preview_only", "can_execute": False, "agent_id": agent_id,
            "inventory_revision": snapshot.get("revision"), "default_action": "soft_delete_agent_keep_data",
            "schedule_action": "disable_and_drain_before_unlink", "tables": output,
            "history_count": snapshot["agents"][agent_id].get("history_count"),
            "history_action": "retain", "data_preserved": True,
            "admin_cleanup": "future_separate_admin_task", "cleanup_available": False}


class SchemaPlanningAPI:
    """Unwired API skeleton: caller must supply an authenticated tenant principal."""

    def __init__(self, repository):
        self.repository = repository

    def handle(self, operation, principal, agent_id, body):
        if not principal or not principal.get("tenant_id") or not principal.get("user_id"):
            return 401, {"code": "authentication_required"}
        if "schema:preview" not in principal.get("capabilities", []):
            return 403, {"code": "schema_permission_required"}
        if operation == "confirm_delete" and (not isinstance(body, dict) or
                body.get("mode", "keep_data") != "keep_data" or "table_ids" in body):
            return 400, {"code": "agent_delete_must_keep_data"}
        if operation in {"apply_schema", "confirm_delete"}:
            return 501, {"code": "lifecycle_mutations_not_implemented", "can_execute": False}
        if operation not in {"preview_schema", "delete_impact"}:
            return 404, {"code": "not_found"}
        tenant_id = principal["tenant_id"]
        try:
            resource_id(agent_id)
            if not self.repository.can_access_agent(tenant_id, principal["user_id"], agent_id):
                return 404, {"code": "agent_not_found"}
            snapshot = self.repository.snapshot(tenant_id)
            if operation == "preview_schema":
                manifest = body.get("manifest", {})
                if manifest.get("agent_id") != agent_id:
                    raise ValueError("Manifest agent mismatch.")
                return 200, preview_schema(tenant_id, manifest, snapshot)
            return 200, delete_impact(tenant_id, agent_id, snapshot)
        except PermissionError:
            return 403, {"code": "tenant_mismatch"}
        except (ValueError, TypeError, KeyError, AttributeError):
            return 400, {"code": "invalid_schema_request"}


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    print(json.dumps({"schema": preview_schema(fixture["tenant_id"], fixture["manifest"], fixture["snapshot"]),
                      "delete": delete_impact(fixture["tenant_id"], fixture["manifest"]["agent_id"], fixture["snapshot"])}, indent=2))
