# Agent-Owned CellX Schemas

Status: architecture plus read-only planner and **deployed admin-only registry preview**,
2026-09-14. No business tables created, altered or deleted. New
`server.py` handlers are feature-gated OFF by default and explicitly enabled on AWS;
Builder controls, routes,
scheduler configuration and existing drafts are unchanged. SQLite registry
mutations are limited to schema drafts and their retained metadata/history.
See [the implemented registry API contract](AGENT_SCHEMA_REGISTRY_API.md) for the
current endpoints and tests. Sections below describe the broader target design;
verified customer tenancy and physical DDL are not implemented.

Latest user policy: Agent-created business tables use the `agent_` prefix.
Deleting an Agent retains **all tables, fields, relationships and historical data**.
There is no ordinary Agent-delete option to drop tables, including exclusive ones.
Cleanup/archival is a separate future administrator task, not implemented here.

## What Exists Today

Inspection covered the extension source, local SQL, Builder persistence, scheduler
and live **column metadata only**, not customer records. The live `cellx_base`
database reported 72 tables at inspection time.

| Area | Evidence | Consequence |
| --- | --- | --- |
| Organization and users | Live `sys_user.dept_id`, `sys_dept`, `sys_role.data_scope`, `sys_register.dept_id/dept_belong_id` | Organization concepts exist in base CellX; they do not prove tenant isolation in this extension. The base Java application source is not in this workspace. Department-to-company membership semantics still need verification. |
| Table metadata | Live `gen_table`, `gen_table_column`; `server.py:cellx_schema()` reads `information_schema` | Page/code-generation metadata exists, but no Agent ownership, canonical entity identity, company scope or reference registry was found in the inspected code. Do not equate `gen_table` with an ownership registry. |
| Current writes | `execute_cellx_bulk_import()` requires an existing physical table and `approved_write`, then uses server-wide MySQL credentials | The DB node does not create tables. Missing mapped fields are skipped. Deduplication is special-cased to `provider_listing_id`. `owner='workflow'` and `dept_id=0` defaults are not a tenant boundary. |
| Current table creation | `sql/create_cx_orderdesk_order.sql` is a manually maintained DDL script | Creating a physical table does not automatically register a CellX page, menu, permissions or generated backend code. |
| Agent persistence | `app.js:workflowSnapshot`, `persistWorkflowStore`, `normalizeWorkflow` | Ordinary drafts and per-node config live in localStorage. Unknown manifest properties will be lost unless all normalize/import/export/snapshot paths are extended. |
| Server persistence | `workflow_scheduler.py:normalized_workflow`, `WorkflowScheduler.save` | Daily schedules persist workflow JSON in private SQLite keyed only by workflow ID; no tenant key or canonical Agent record. Normalization also drops unknown manifest fields. |
| Templates | Static template JSON/manifest and JSON marketplace store | A reusable template is different from an installed company Agent. They must have separate identities and deletion policies. |
| Delete today | `app.js` workflow tab close filters the local workflow list; `delete_workflow_template_file()` deletes template files; `delete_marketplace_template()` removes a listing | None implements Agent soft deletion or database impact preview. Closing a tab does not disable a saved server schedule. Do not attach DROP TABLE to these handlers. |
| Authorization | Management uses a global admin token; marketplace sessions have users but no verified company membership | A caller-provided company ID, email or role is not sufficient permission for schema access. |

### Security Gates Before Any Mutation

- `GET /cellx-db/schema` and ordinary `/integrations/test` database dispatch currently
  do not enforce per-tenant schema access. A new protected lifecycle API alone is
  insufficient: legacy DB query/write and scheduled/script paths could bypass it.
- Marketplace registration accepts an `admin` role value; template deletion's
  owner check can use caller-supplied `developerEmail`. Do not reuse either as
  company-owner authority. These are pre-existing findings, not modified here.
- Define authenticated server-resolved company membership and permissions first;
  deny unknown company IDs and cross-company table references. Never derive
  tenancy from `dept_id=0`, matching email domains, workflow names or model output.
- Managed tables must be denied by legacy raw-name endpoints until a verified
  tenant+Agent binding is supplied. Arbitrary SQL filters and global DB credentials
  must not become a customer-facing path around that check.
- Unrestricted scripts/external Agents with shared database credentials can bypass
  application checks. Keep those operator-only; use isolated credentials and
  tenant-scoped gateway capabilities for customer Agents.

## Target Model

Use a MySQL control-plane registry beside business tables, not browser state as
the authority. Use UUID IDs, UTC timestamps, explicit versions and foreign keys
with RESTRICT, never CASCADE into business data. Proposed metadata tables below
are specifications, not a migration applied to the existing database.

| Table | Required fields and constraints |
| --- | --- |
| `cad_tenant` | `id PK`, `name`, `state`, verified mapping to base company/dept identity; no inferred migration |
| `cad_membership` | `(tenant_id,user_id) PK`, role, state; only privileged owner invitation can change role |
| `cad_agent` | `(tenant_id,id) PK`, name, `template_id nullable`, state, workflow version, manifest version, deleted_at/by, deletion_job_id; keep legacy workflow ID in a separate unique tenant mapping |
| `cad_agent_revision` | `(tenant_id,agent_id,version) PK`, secret-free workflow JSON, manifest JSON, manifest_hash, actor/time; execution secrets referenced separately |
| `cad_table_registry` | `(tenant_id,id) PK`, connection_id, physical_table_name, display_name, entity_key, entity_version, scope, created_by_agent_id, owner_agent_id nullable, schema_hash, registry_version, state, usage_status, managed/adopted flags, retention policy |
| `cad_entity_binding` | unique `(tenant_id,scope_key,entity_key,entity_version)` -> table_id; company scope_key is `company`, exclusive scope_key is the owning Agent ID |
| `cad_agent_table_use` | `(tenant_id,agent_id,table_id) PK`, read/write permission, active/retained/unlinked state, adopted_by, timestamps; field access recorded separately; never trust a client usage_count |
| `cad_field_registry` | `(tenant_id,table_id,field_id) PK`, unique physical field name per table, logical type and full normalized physical definition, creator_agent, shared flag, state, version |
| `cad_agent_field_use` | `(tenant_id,agent_id,table_id,field_id) PK`, permissions, state; dropping an Agent does not implicitly drop its columns |
| `cad_relationship_registry` | `(tenant_id,id) PK`, source/target table+field IDs, cardinality, physical FK/index names, creator_agent, constraint state, version; endpoints must belong to same tenant |
| `cad_agent_relationship_use` | `(tenant_id,agent_id,relationship_id) PK`, retained reference state and timestamps |
| `cad_schema_plan` | tenant, agent, plan_id PK, kind, actor, canonical request, hash, inventory revision, expires_at, state; immutable server snapshot, no execution secrets |
| `cad_schema_job` | job_id PK, tenant, agent, plan_id, idempotency key unique per tenant+operation, state, per-operation checkpoints, error codes, actor/time |
| `cad_lifecycle_audit` | append-only actor, tenant, Agent, plan/job, target IDs, before/after hashes, operation outcome; no row bodies or credentials |

`usage_count` is derived from authoritative active/retained references, not a
mutable client counter. Creator, current owner and consumers are separate facts.
Soft-deleted Agents retain audit and history links. Their active bindings are
revoked/unlinked, while historical references remain for administrator review.
All composite references include tenant_id. Physical name is unique within its
connection and follows `agent_<entity_key>_<scope_digest>`, for example
`agent_customer_596204e2b187e9352d5a3fac`. The entity key must match
`[a-z][a-z0-9_]{0,47}`; reject invalid characters instead of silently folding
different names together. Physical names contain only lowercase letters, digits
and underscores. Retain at most 33 entity characters plus `agent_`, a separator
and a 24-character SHA-256 suffix: at most 64 characters for MySQL.
Hash the full untruncated entity key, tenant and scope, plus Agent ID for private
tables. Same-company shared entities produce the same name across Agents; other
companies or private owners produce different names. The repository supplies an
authoritative occupied-name set including unmanaged physical tables. A collision
blocks preview; apply must recheck under locks and a connection-wide unique name
constraint. Never overwrite, auto-adopt or randomly rename an occupied table.
The `cad_*` names above are operator-owned control-plane metadata tables, not
Agent-created business tables; existing tables are not renamed by this policy.

### Isolation and Shared Entities

For the first production iteration, use tenant-specific physical tables with
same-company sharing. Do not pool different companies' customer/order rows into
one new business table. Higher table count is an explicit tradeoff for simpler
isolation; add quotas and move large tenants to private databases later.

Use a reviewed entity catalog (`company`, `customer`, `order`, `product`, etc.)
with schema version and semantic contracts. A same-name table is only a suggestion.
Automatically reuse only a registered same-company, same-scope, compatible
canonical entity. Ambiguous matches, existing unmanaged tables, and incompatible
field types require review. New private tables remain private; another Agent
must receive an explicit audited share grant or use its own table.

Do not automatically adopt existing `cx_orderdesk_order`, `cx_orders_management`,
`sys_*` or `gen_*`. Adoption requires verified company ownership, a complete
dependency inventory, duplicate/data-type checks, backup and an explicit mapping.
Mixed-company legacy tables need an isolation migration first. Existing IDs and
records are preserved; UUID id is the new-table convention, not a rewrite of
legacy BIGINT keys. Adopted legacy tables are never eligible for automatic drop.

## Manifest and Reconciliation

Runnable fixture: `examples/agent-schema-preview.json`. It models a research Agent
sharing `customer` with a sales Agent, adding an optional `industry` field and
using an exclusive `agent_recommendation_b5978dc7b65b1c1a9765bb5f` table related
to customer. Delete preview lists both retained physical names and preserved rows.

The prototype's logical types are deliberately limited. Production must extend
the manifest with validated string lengths, decimal precision/scale, uniqueness,
indexes, relationship cardinality and physical type compatibility. Unsupported
definitions must block approval, never be silently shortened or treated as SQL.
The model proposes a manifest, not executable DDL or permissions. Schema changes
are approved at Agent setup/update, not on each run or first scraped record.

1. Authenticate; resolve company, Agent access and schema capabilities on server.
2. Load registry plus MySQL columns/indexes/FKs/views/triggers and recorded script,
   page, external-runner and scheduler dependencies. Unknown dependencies prevent
   labeling a retained table unused; they do not authorize any cleanup.
3. Validate manifest and quotas; reconcile only with scoped canonical bindings.
4. Preview create/reuse, nullable additions, index/FK proposals, conflicts and cost.
   Never infer DROP/RENAME/narrowing from missing fields. Required additions need
   a separate validated backfill; FK additions need type/index/orphan validation.
5. Persist expiring plan bound to actor, tenant, Agent+registry revisions and hash.
6. On apply, reauthorize, lock canonical bindings/table registry and recompute drift.
   Reject stale plans with 409. Idempotency replays return the original job.
7. An isolated DDL worker applies allowlisted additive statements with checkpoints.
   MySQL DDL auto-commits: do not pretend a SQL transaction can roll it all back.
   Resume by introspecting actual schema; quarantine partial operations instead
   of deleting possibly populated tables to roll back. Use an advisory lock on
   the same persistent connection, not across separate `mysql` CLI invocations.
8. Publish table/field/relationship bindings only after verification. Execute DB
   nodes by registered table ID resolved server-side, not LLM physical names.
9. A separate CellX adapter updates verified page-generation metadata and permissions
   through the base application's supported API. Until investigated, new tables
   are usable through the Agent data view but must not be advertised as auto-created
   CellX CRUD pages. Never write guessed rows into `gen_table`/`sys_menu`.

## Delete Lifecycle

UI must distinguish **Close Tab**, **Unpublish Template** and **Archive Agent**.
There is no Delete Exclusive Data control in the Agent deletion flow.
Existing template operations must never cascade into
installed Agents or company tables.

The only planned Agent deletion mode is keep-data, through a lifecycle job:

1. Resolve authorized Agent; display schema, rows/history, field/relationship
   consumers, current schedules/runs, other consumers, retention and dependencies.
   Unknown row counts display "Unknown", not zero. Show estimate/exact timestamp.
2. Set Agent `deleting`, disable schedules, block new manual/queued/runner starts.
   Running jobs must drain or be explicitly stopped at safe boundaries. A delete
   preview is not a lock; everything is checked again on confirmation.
3. Soft delete Agent, revoke runtime table access and unlink active consumers.
   Retain field/relationship/history references in the archive and keep all data.
   Tombstones prevent an old browser Save Draft from silently resurrecting it.
4. List every retained physical table, creator/owner, field and relationship
   consumers, known/unknown data counts and preserved history. Mark shared/in-use
   tables `retained_in_use`; mark a managed table with no other references or
   dependencies `unused_orphaned` only when inventory and retention facts are
   complete. Otherwise use `retained_review_required`. These are registry usage
   labels, not business row updates, table renames or permission to delete.
5. Hold table/use locks during unlink and recheck revisions. Stale previews get
   409. Retain all columns, indexes, FKs, tables and history even when the Agent
   was their only consumer. No CASCADE or second destructive confirmation.
6. Audit soft deletion/unlink, retained table IDs and usage labels. Retry through
   checkpoints; report partial completion honestly. Restoring an Agent is explicit
   and requires current membership and new binding checks, not automatic activation
   of an old browser draft or schedule.

### Future Administrator Cleanup or Archival

This is outside the Agent-delete API and current prototype. The preview only says
that retained tables may be reviewed by an administrator later; it exposes no
drop eligibility, cleanup action or executable job. Any future implementation
needs a separately approved admin-only contract, reference/dependency and retention
review, active-job draining, locking, backup and restore drills, auditable approval
and idempotent recovery. Shared, adopted and system tables remain protected.
An `unused_orphaned` label alone is never sufficient authorization to remove data.

The current SQLite scheduler needs a tenant-aware canonical Agent mapping and
claim-time tombstone/lease checks before any of the above can be activated. Merely
setting enabled=0 does not drain already-running execution or stop manual runs.

## API Contract and Skeleton

Proposed prefix: `/ext-api/agents/{agent_id}`. These are **not live endpoints**.
`agent_schema_planner.SchemaPlanningAPI` is a pure adapter skeleton using a future
server-side repository. No framework, DB connection or new `server.py` route is
added. The principal must come from verified session middleware, never request JSON.

| Method/path | Request | Result |
| --- | --- | --- |
| POST `/schema/preview` | `{manifest, expected_agent_version}` | changes, conflicts, matches, field/relationship consumers; production adds plan_id/hash/expiry/revisions |
| POST `/schema/apply` | `{plan_id, plan_hash, expected_agent_version, idempotency_key}` | 202 job_id; reauthorization and schema:apply required |
| GET `/delete-impact` | no client registry or SQL; optional include_counts flag | retained physical tables/fields/relationships/history, data_preserved=true, post-unlink usage labels, running jobs, production plan_id |
| POST `/delete` | `{plan_id, plan_hash, mode:"keep_data", idempotency_key}` | 202 soft-delete/unlink job; agents:delete required; keep_data is the only supported mode |
| GET `/lifecycle-jobs/{job_id}` | no credentials | durable progress, retained targets and partial failures |

Reject destructive modes such as `drop_exclusive` and explicit `table_ids` cleanup
requests with 400. Do not silently downgrade a destructive request to successful
soft deletion. A future administrator cleanup service needs its own API and policy.

Errors: 400 malformed manifest, 401 no session, 403 forbidden/mismatched tenant,
404 inaccessible Agent, 409 stale/in-use/conflicting schema, 422 unsupported
physical migration, 429 quota, 503 unavailable dependency. Raw MySQL errors and
cross-company metadata must not be disclosed. Mutations use CSRF protection when
cookie authenticated, restrictive CORS and no credentials in query strings.

Skeleton operations `preview_schema`/`delete_impact` use repository-scoped snapshots.
Valid `apply_schema`/keep-data `confirm_delete` requests return **501**; destructive
delete requests return 400. Every preview returns `can_apply:false` or
`can_execute:false`. Delete preview also returns `data_preserved:true`,
`cleanup_available:false` and `admin_cleanup:"future_separate_admin_task"`.
There is no drop-candidate output or second-confirmation deletion capability.

Repository interface to implement first:

```python
can_access_agent(tenant_id, user_id, agent_id) -> bool
snapshot(tenant_id) -> dict  # registry + verified, scoped dependency metadata
```

The offline CLI accepts a fixture for developer testing only. HTTP clients must
never supply inventory, ownership, row counts, references, revisions or principals.
`snapshot.occupied_physical_names` must come from connection-wide physical metadata,
not a client list. It is used internally to block collisions and must not leak
other tenants' names. Snapshot field definitions must be canonical logical projections; physical drift
must be resolved by the repository before any production plan is actionable.

## Builder UI Design

Keep the current toolbar and `/agent/` route unchanged. Add an **Agent Data** tab
inside Properties after canonical server persistence is ready.

- Summary: company name (server-resolved), Agent status, manifest version.
- Table grid: Entity / Physical table / Shared or Exclusive / Creator / Consumers /
  Desired changes / Status. Expand a row for fields, relationships and dependents.
- Existing-table picker only lists authorized same-company entries. Reuse is the
  first choice for exact compatible matches. Ambiguity opens a picker; no AI auto-merge.
- Preview button opens an accessible dialog; Apply disabled on conflicts, unknown
  ownership, missing permissions, stale plan or unsupported types. Use accessible
  loading/error states and preserve form drafts when requests fail.
- Archive dialog has separate sections for shared retained tables, exclusive
  retained tables, fields/relationships and execution/history impact. Show the full
  `agent_` physical names, "Data retained" status and expected unused/review labels.
  All data is retained, without delete-table checkboxes or a second destructive
  dialog. A non-actionable note explains that administrators may review retained
  tables in a future separate cleanup/archival process.
- UI uses semantic tables, fixed readable columns, horizontal/vertical scrolling,
  focus containment, Escape/Close, and returns focus to the initiating control.
  Show Deleted/Deleting states on reload and prevent Save Draft/run after tombstone.
- Close Tab is only UI navigation in the new design; migrating existing behavior
  requires separate browser-tab state from the persisted Agent collection. Explain
  this change to users rather than silently treating current tab close as archive.

## Delivery Stages and Files

### Delivered Now: Isolated Prototype

- `agent_schema_planner.py`: strict manifest validation, scoped exact shared reuse,
  safe `agent_` name generation/collision blocking, nullable-field proposals,
  immutable previews, retain-only deletion impact and dependency-aware usage labels,
  unwired API adapter with disabled mutations; standard library only.
- `examples/agent-schema-preview.json`: fictitious two-Agent company fixture.
- `test_agent_schema_planner.py`: isolation, reuse, incompatibility, dependency,
  retention, API authorization and no-mutation regression cases.
- This document: database model, API/UI contracts, reconciliation/deletion and rollout.
- `agent_schema_registry.py`, `test_agent_schema_registry.py`: persistent SQLite
  metadata, admin-only request handling, expiring previews, dry-run apply and
  retain-only deletion of registry schema drafts. `server.py` wires these under
  `/agent-schemas/`, disabled by default. No MySQL driver or DDL execution path.
- `AGENT_SCHEMA_REGISTRY_API.md`: implemented API, configuration, scope limits and
  verification. The older `SchemaPlanningAPI` remains an offline adapter example;
  the current server uses the new registry service, not that unwired class.

### Phase 1: Identity and Read-Only Inventory

Create `agent_registry.py` (repository/versions/access), `agent_auth.py` (verified
base identity bridge), and reviewed `sql/agent_registry_v1.sql` control-plane
migration. Add session+membership checks in `server.py`; resolve legacy DB gateway
exposure before allowing customer-managed schemas. Add narrowly gated preview
handlers that import this planner. New feature flag defaults OFF. Do not use the
global management token as company identity.

Update `app.js` snapshot/normalization/import/export, `index.html` Properties panel
and scoped `styles.css` for Agent Data preview. General Agent persistence must use
the registry, with explicit tenant-bound import of browser drafts, preserved legacy
IDs and provenance, no leaked credentials. Extend `workflow_scheduler.py` with
versioned tenant mapping without discarding existing schedule/run rows. Start with
an internal test tenant and metadata-only adoption review. No DDL worker yet.

### Phase 2: Additive Apply

Add `agent_schema_jobs.py` and a separately privileged worker, vetted type/index/FK
compiler, job table/outbox, locks/leases, quotas and audit. Database driver must
support persistent parameterized transactions/advisory locks. Wire apply only
after simulated retry/partial-DDL recovery succeeds. New managed DB nodes bind
table IDs, scoped to registered Agent capabilities. Investigate base CellX's
supported page-generation API before promising automatic backend CRUD pages.

### Phase 3: Safe Archive, Unlink and Retain

Add `agent_delete_planner.py` and lifecycle job orchestration with scheduler/runner
draining and tombstones. Support only Agent soft deletion, unlink and retained-table
usage labels. All tables and historical data remain. Existing templates and
marketplace deletion keep their separate responsibilities. Future administrator
cleanup/archival is a separately scoped project, not a hidden option in this phase.

### Release Gates

Test two companies with identical entity names, two same-company Agents sharing
customer, private tables, ambiguous adoption, wrong/missing auth, stale preview,
double apply, physical-name collisions and truncation, concurrent create/link/unlink/run,
retained consumers, unknown count, rejected destructive delete modes,
partial DDL, worker crash, FK orphan/type errors, backup restore, soft deletion
while a daily run is queued/running, old-browser resurrection and template deletion.
Test UI at mobile/desktop widths and keyboard-only use. Regression-test existing
daily order imports, health, `/agent/` and legacy `/workflow/` compatibility.

Run the delivered offline tests and demo from `cellx-extension-api`:

```powershell
python -m unittest test_agent_schema_planner -v
python agent_schema_planner.py examples/agent-schema-preview.json
```

The restricted registry preview is deployed, but customer-facing schema access
and business DDL are not appropriate yet: verified tenant identity, legacy DB
access enforcement and scheduler lifecycle synchronization remain prerequisites.
The preview leaves existing workflows and business-data behavior unchanged.
