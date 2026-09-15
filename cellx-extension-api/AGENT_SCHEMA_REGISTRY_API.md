# Agent Schema Registry API: Admin-Only Preview

Deployed to AWS on 2026-09-14 as **admin-only registry preview**. Source defaults
OFF; the AWS service explicitly enables the preview through its own drop-in.
The implementation
has no MySQL connection, SQL compiler, DDL executor, or switch that enables real
schema apply. It is a persistent control-plane prototype, not customer tenancy
or an end-to-end replacement for the current Builder/scheduler lifecycle.

## Capabilities and Boundaries

| Capability | Current implementation |
| --- | --- |
| Tenant/company scope | Operator creates explicit tenant records. A valid server-configured global admin token is required on every endpoint. This is admin-only scope selection, not a browser-asserted customer identity. |
| Agent registration | Server generates a fresh `asr_<uuid>` schema-draft ID. It cannot import or claim ownership of arbitrary existing workflow IDs. |
| Persistence | Dedicated private SQLite file with schema version/application ID, foreign keys, transactional updates and uniqueness constraints. Existing unrelated databases are rejected. |
| Manifest save | Saves versioned, validated schema intent and metadata-only table/field/relationship usage. Additive metadata: preserves omitted fields and retained references. |
| Shared table reuse | Same tenant + company scope + entity key shares one registry binding. Agent scope uses owner ID; different tenants use separate names. Physical names use `agent_<entity>_<scope hash>`. |
| Preview | Reads server-side saved manifest/registry. Does not accept a client inventory, SQL, ownership map or list of other Agents. |
| Apply | Only explicit JSON `dry_run:true`; returns `executed:false`. Missing/false/string values get 501. Never executes CREATE/ALTER against business data. |
| Delete | Soft deletes/unlinks **only the new registry schema draft**, retaining all metadata/history/table definitions. Does not delete an existing Builder tab, template, schedule or business table. |
| Runtime protection | A read-only scheduler lookup blocks deletion if that schema-draft ID has any schedule/run record; lookup errors also block. There is no atomic runtime lease bridge yet. |
| Actual business tables | Not created, inspected, adopted or renamed. All table registry entries remain `state:"planned"`; `physical_exists:null` means unknown, not a successful schema check. |
| Customer UI/auth | Not added. Existing marketplace email/role and global DB endpoints are not promoted into tenant authority. |

Registry metadata sharing is not database access authorization. The legacy
`cellx-db` schema/query/write/script paths remain as before. Because they lack
complete tenant enforcement, **real DDL and customer-facing schema access must
remain disabled**. Enabling this feature does not resolve those pre-existing gates.

## Configuration

- `AGENT_SCHEMA_ENABLED=false` by default. `true` enables these admin-only APIs,
  not business DDL. There is deliberately no real-apply environment flag.
- `AGENT_SCHEMA_DB` defaults to `agent-schema-registry.sqlite3` next to `server.py`.
  Use a dedicated path. The factory rejects paths aliasing scheduler, analytics or
  marketplace storage. Initialization refuses unrelated SQLite databases.
- `WORKFLOW_MANAGEMENT_TOKEN` is the existing server-side admin secret, falling
  back to `MARKETPLACE_ADMIN_TOKEN` under the existing server convention. Missing
  configuration returns 503. Never put secrets in a URL or JSON request body.
- `AGENT_SCHEMA_ALLOWED_ORIGIN` defaults to `https://app.cellaidata.com`. A supplied
  non-matching Origin gets 403. Command-line calls without Origin still require
  the token. These routes emit no cross-origin access grant.

Every request uses `X-Workflow-Admin-Token`. No token in `developerEmail`, `role`,
`adminToken` body, session body or query string is accepted. The registry is only
opened after successful feature/auth checks. Responses are `Cache-Control:
no-store`. New POST routes enforce a 256 KiB body limit. Failures return stable
error codes without DB paths, credentials, SQL or exception traces.

## Persistence Model

The SQLite migration initializes atomically on the first authorized request:

- `tenants`: operator-defined scope, global scope revision, creation audit identity.
- `agents`: unique server-generated ID, tenant, active/deleted state, manifest and
  optimistic version; tombstones prevent save-after-delete.
- `table_registry`: unique scope/entity binding, unique planned physical name,
  creator/owner, normalized field definitions, field creators, schema hash,
  timestamps, `state=planned`, and `usage_status`.
- `table_use`: composite tenant+Agent+table references with active/retained state,
  field use and logical relationship definitions. Composite FKs prevent cross-tenant
  associations. Relationships remain metadata, not physical FK constraints.
- `agent_revisions`: immutable historical manifests. Omitted tables/fields are
  preserved in previous revisions, not removed from the registry.
- `plans`: persisted expiring schema/delete previews bound to tenant, Agent,
  scope revision, Agent version and plan hash; completed deletion receipt for retry.
- `audit`: operator actions, versions/hashes and plan IDs; no credentials or row data.

The file has POSIX mode 0600, standard SQLite rollback journaling and a dedicated
application ID. On Windows, access follows the containing directory ACL. Back up
using SQLite's backup API or while stopped; do not copy a live file without its
journal. The default database and sidecars are excluded from Git.

Table definitions are `planned_in_use` while any active schema draft refers to
them; after the last unlink they become `unused_planned`. This is only metadata
usage, not a declaration that a physical table is empty, unused or safe to drop.
Old references remain `retained` and continue to appear in review/history.

## Endpoints

Prefix: `/ext-api/agent-schemas/` (also `/agent-schemas/` for a local API server).
Except `GET status`, all operations below use POST with JSON and the admin header.

### 1. Create Scope and Draft

`POST tenants/create`

```json
{"tenant_id":"demo_company","name":"Demo company"}
```

`POST agents/create`

```json
{"tenant_id":"demo_company","name":"Customer research schema"}
```

Returns `agent_id:"asr_..."`, `version:0`, `runtime_integrated:false`. These records
are new schema drafts; they do not prove membership in an existing CellX company.
Existing tenant IDs return 409 rather than overwriting ownership.

### 2. Save Manifest

`POST manifest/save`, using the ID returned above:

```json
{
  "tenant_id":"demo_company",
  "agent_id":"asr_REPLACE_WITH_RETURNED_ID",
  "expected_version":0,
  "manifest":{
    "version":1,
    "tenant_id":"demo_company",
    "agent_id":"asr_REPLACE_WITH_RETURNED_ID",
    "tables":[{
      "entity_key":"customer",
      "scope":"company",
      "fields":[
        {"name":"id","type":"uuid","nullable":false},
        {"name":"email","type":"string","nullable":true}
      ]
    }],
    "relationships":[]
  }
}
```

Response increments Agent version and returns planned table metadata plus
`business_ddl_executed:false`. Same-company compatible definitions are reused;
types cannot be changed or fields implicitly removed. New optional fields can be
added to the metadata union. Conflicts roll back the whole registry operation.
Full entity keys contribute to the name hash before readable-name truncation;
registry collisions block save. Names are not checked against MySQL yet.

### 3. Preview and Dry-Run Apply

`POST schema/preview`

```json
{"tenant_id":"demo_company","agent_id":"asr_REPLACE_WITH_RETURNED_ID"}
```

Response includes `plan_id`, `plan_hash`, `expires_at` (Unix seconds, 15 minutes),
actions such as `reuse_planned_table`, and `physical_inventory_verified:false`.
The preview is based on the saved manifest, not a client-provided action list.
Relationship additions stay `review_relationship` proposals.

`POST schema/apply`

```json
{
  "tenant_id":"demo_company",
  "agent_id":"asr_REPLACE_WITH_RETURNED_ID",
  "plan_id":"REPLACE_WITH_PREVIEW_ID",
  "plan_hash":"REPLACE_WITH_PREVIEW_HASH",
  "dry_run":true
}
```

Response: `mode:"dry_run"`, `executed:false`, `business_ddl_executed:false`.
There is no create/drop business SQL behind this endpoint. Registry audit records
the dry run, but physical state and saved schema versions do not change. Any
Agent/schema mutation in the scope invalidates old plans (409). Repeated valid
dry runs return the same proposal and may append audit events.

### 4. Delete Impact and Registry Soft Delete

`POST delete-impact` with the same tenant/Agent pair returns a persisted deletion
plan and list of retained `agent_` names, metadata, field/relationship consumers,
unknown physical row counts and `data_preserved:true`.

`POST delete`

```json
{
  "tenant_id":"demo_company",
  "agent_id":"asr_REPLACE_WITH_RETURNED_ID",
  "plan_id":"REPLACE_WITH_DELETE_IMPACT_ID",
  "plan_hash":"REPLACE_WITH_DELETE_IMPACT_HASH",
  "mode":"keep_data"
}
```

In one SQLite transaction, rechecks the plan and runtime guard, marks the schema
draft deleted, retains all table/field/relationship definitions and history, and
changes active bindings to retained. It returns `registry_updated:true`,
`lifecycle_scope:"registry_schema_draft_only"` and per-table `registry_usage_status`.
Retrying the identical completed plan returns its receipt without replaying changes.
Deleted drafts cannot be silently saved/restored. Other Agents' active bindings
remain unchanged. No hard-delete, physical cleanup, or restore endpoint exists.

An existing runtime schedule/run record causes 409, without disabling or altering
that schedule. The lookup is a guard, not a race-free scheduler lease or an
end-to-end workflow archive. Never use this API to promise an existing Builder
Agent has been stopped. Runtime lifecycle integration remains a separate gate.

`drop_exclusive`, explicit `table_ids` and unexpected fields are rejected with
400. A separate future administrator archival/cleanup project is still required.

## Verification and Release

```powershell
python -m unittest test_agent_schema_registry test_agent_schema_planner test_workflow_scheduler -q
```

Tests use temporary SQLite files and local threaded HTTP servers. They cover
unauthorized/disabled requests without storage creation, forged identity fields,
Origin/body/cache behavior, persistence/reopen, unrelated-database rejection,
schema conflicts and transaction rollback, stale/expired plans, concurrent sharing,
cross-company denial, explicit dry-run-only apply, retained/idempotent deletion,
runtime guard failures, full HTTP round trip and existing scheduler/route regressions.
Business MySQL calls are explicitly prohibited by mocks in the apply/HTTP tests.

AWS deployment and HTTPS smoke verification completed on 2026-09-14. A dedicated
0600 SQLite registry was initialized; no business database was accessed or modified.
Source defaults remain disabled, while AWS explicitly enables admin-only preview.
See [the deployment record](AGENT_SCHEMA_REGISTRY_DEPLOYMENT.md) for checks,
backup and retained synthetic metadata. This must not be advertised as automatic
business table creation. Before customer access or real additive DDL, implement verified membership,
canonical Agent/runtime identity and leases, close legacy DB/script bypasses,
inspect authoritative MySQL schema and dependencies, and add a tested DDL worker
with drift checks, privilege separation, job checkpoints and recovery.
