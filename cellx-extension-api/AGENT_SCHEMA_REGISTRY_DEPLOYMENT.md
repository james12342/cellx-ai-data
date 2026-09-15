# Admin-Only Registry Preview Deployment

Verified 2026-09-14, approximately 07:37 UTC.

## Published Scope

- Existing AWS API service: `cellx-extension-api`, `/opt/cellx-extension-api`.
- Published `server.py` registry-only delta, `agent_schema_registry.py`,
  `agent_schema_planner.py` and these registry documents.
- The deployed server was built from freshly retrieved live source. Unrelated
  local portable-route, Stripe-default and Instagram-copy edits were excluded.
- No Nginx/UI assets/routes, scheduler source, workflow definitions or business
  tables were changed. The API service was restarted once after checking no active
  runs or enabled schedules. A brief scheduler claim lock guarded the restart;
  logical schedules/runs/steps fingerprints matched before and after deployment.
- Backup: `/tmp/cellx-before-registry-preview-qdj0ehbw/server.py`.
- Reviewed candidate/tests: `/tmp/cellx-registry-preview-20260914/`.

## Configuration and Storage

Drop-in: `/etc/systemd/system/cellx-extension-api.service.d/agent-schema.conf`.

```ini
[Service]
Environment="AGENT_SCHEMA_ENABLED=true"
Environment="AGENT_SCHEMA_DB=/opt/cellx-extension-api/agent-schema-registry.sqlite3"
Environment="AGENT_SCHEMA_ALLOWED_ORIGIN=https://app.cellaidata.com"
```

The existing server-configured `WORKFLOW_MANAGEMENT_TOKEN` is reused through the
`X-Workflow-Admin-Token` header; no secret was copied into scripts, docs or logs.
The new SQLite file is dedicated control-plane storage, mode 0600. It is not the
scheduler, analytics, marketplace or business database. Initialization was performed
by the first authenticated status request. No MySQL operation was executed.

Status, when authenticated, reports:

```json
{
  "ok": true,
  "storage": "sqlite",
  "registry_version": 1,
  "admin_only": true,
  "preview_enabled": true,
  "real_apply_enabled": false,
  "runtime_integrated": false
}
```

## Verification

- AWS Linux candidate: 52 tests passed (21 registry, 19 planner, 12 scheduler).
  The portable-router-only test was excluded because those unrelated local route
  changes were not deployed. The complete local suite had 53 passing tests.
- Public HTTPS status without token: 401, including forged JSON role/email.
- Public HTTPS status with the existing admin token: 200, preview enabled,
  real apply disabled. Disallowed Origin: 403.
- Authenticated tenant/schema-draft creation, manifest save, shared binding reuse,
  schema preview and explicit `dry_run:true`: succeeded; executed=false.
- Missing/false dry_run: 501. Destructive deletion mode: 400. Wrong tenant: 404.
- Registry soft delete and identical retry: succeeded; all definitions and history
  retained, other schema drafts' bindings unaffected.
- API health: ok=true, scheduler.running=true, 15-second polling.
- Existing `/agent/` and `/workflow/` compatibility remain under unchanged Nginx
  configuration; no UI links or styles were modified by this deployment.

## Deliberate Test Metadata

The smoke test created only synthetic control-plane entries:

- Tenant `registry_smoke_20260914_073726`.
- Two schema drafts, both soft-deleted after verification.
- One shared planned `agent_deployment_probe_...` table definition, retained as
  `unused_planned`; two retained references and audit/revision/plan records.

There is no business table corresponding to a successful DDL operation: none was
attempted. Physical MySQL existence was not queried; status remains unknown.
Test metadata is intentionally retained to exercise the keep-data policy. Report:
`/tmp/cellx-registry-preview-smoke-report.json` (no credentials).

## Disable or Roll Back

To disable preview, change only the dedicated drop-in flag to false, reload systemd
and restart the API during a safe window after checking active jobs. Retain the
registry file and all existing environment/secrets. For a code rollback, restore
the backed-up server and remove only this feature's drop-in after an operational
review; do not roll back or delete scheduler/business data. The installer already
included automatic rollback for startup/auth/health verification failure.

Real schema apply remains unimplemented, not merely hidden behind a UI toggle.
No flag in this release can enable physical DDL. Runtime Agent archive integration,
customer membership and legacy DB access isolation remain future work.
