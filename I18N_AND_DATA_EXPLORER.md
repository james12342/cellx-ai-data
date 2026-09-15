# Internationalization and Data Explorer

Deployed September 14, 2026 to the existing AWS host.

## Pages

- Marketing: https://www.cellaidata.com/ and https://app.cellaidata.com/portal/
- Analytics: https://www.cellaidata.com/analytics.html
- Agent Builder: https://app.cellaidata.com/agent/ (including voice, templates, marketplace and schedule UI)
- Data Explorer: https://app.cellaidata.com/data/
- Legacy CellX: https://app.cellaidata.com/ remains the original compiled application, intentionally unchanged.

## Language Behavior

`shared/i18n.js` owns locale selection, explicit message rendering, date display and navigation propagation.
Priority is valid `lang` navigation parameter, shared `cell-ai-data-language` cookie, same-named local storage preference, then the browser's first preferred language.
All `zh` browser locales use Simplified Chinese; other locales use English. The selector saves explicit preferences.
The cookie uses `Domain=cellaidata.com`, `Path=/`, `SameSite=Lax` and HTTPS `Secure`.
Known internal page links carry a language parameter as a storage-free fallback. Only language, never authentication, crosses origins this way.

Static UI uses `data-i18n` and explicit translated attributes. Dynamic messages use `CellI18n.text`, `t` or the Agent UI helpers.
Message parameters are escaped as text; the renderer never scans arbitrary user content for translations.
User inputs, conversation bodies, records, field names, identifiers, JSON, custom Agent/template names and stored settings remain unchanged.
Locale changes affect displayed dates only, not timezone settings, cron values or execution behavior.
Unknown provider/backend text and historical free-form status strings remain verbatim rather than being machine-translated.

Run `scripts/sync_i18n_assets.ps1` after editing shared runtime or CSS. Each frontend owns its Chinese dictionary.

## Data Explorer Access

The new Explorer is administrator-only, read-only, and separate from the legacy frontend.
Enter the existing workflow-management admin token, also used by Agent management. It is kept in session storage (or memory when unavailable), never in static code, URLs or local storage.
The backend validates the trusted `X-Workflow-Admin-Token` header. Frontend email, role, company or Agent claims do not grant access.
Anonymous requests return 401; writes return 405. Responses are `no-store`, and these request URLs are not logged by the API handler.

Routes: `/ext-api/data-explorer/status`, `/catalog`, `/table?table=...`, `/rows?table=...`.
Rows use `page`, `page_size` (maximum 100), `search`, `sort`, `direction`, and optional scalar-equality `filters` JSON.
Identifiers must be valid and found in the server's actual database catalog. Search, filter and pagination values are parameter-bound.
Queries run in a MySQL read-only transaction with rollback, server execution hints and client timeouts.
BIGINT values beyond JavaScript's safe integer range are returned as strings.

The initial column policy is deliberately conservative: credential/personal fields, sensitive tables, unknown text, JSON, binary and long text are masked. Masked columns cannot be searched, filtered or sorted.
Only approved operational text columns and non-sensitive scalar fields are exposed. This is not a universal content-classification guarantee.
Tables without an unmasked primary key have no guaranteed stable pagination order.

Company/Agent grouping comes from read-only registry draft bindings, not runtime ownership or authorization.
Physical existence is checked separately against MySQL. A matching name does not prove deployment, ownership or schema equivalence.
Unlinked real tables remain visibly unlinked. Deleted Agent bindings/data are not removed.
Ordinary-user tenant authorization and runtime-to-registry association are not integrated; do not enable tenant access by trusting client fields.
Registry real schema apply remains disabled. No business DDL or record writes were made.

## Verification and Deployment

- 73 Python tests: Explorer, registry, planner and scheduler.
- 9 shared-runtime browser test groups, including unavailable storage and cross-tab synchronization.
- English/Chinese marketing, analytics, Agent, voice and daily-time browser regressions passed against local and deployed static assets.
- 8 Explorer browser test groups passed against local and deployed assets with mocked APIs; screenshots include desktop and mobile.
- Real candidate and deployed APIs read 72 physical tables and 1 planned binding; real `cx_orderdesk_order` pagination and auth/query/masking checks passed. No record contents or credentials were printed.
- Existing one enabled schedule was preserved; no workflow was running during deployment. Final scheduler health passed.
- Public pages return 200, `/workflow/` redirects to `/agent/`, and unauthenticated Explorer/registry requests return 401.

Cache version: `20260914-i18n-v1`. Voice layout stylesheet remains `20260914-voice-layout-v1`.
PyMySQL 1.2.0 was installed from its hash-verified official wheel into the application directory only; the server has no pip.
Deployment scripts stage only selected changes and guard live hashes. The deployed server preserves unrelated live Stripe/portable behavior.
Backups: `/tmp/cellx-before-data-api-8qchnzmn`, `/tmp/cellx-before-i18n-1hg84xta`, `/tmp/cellx-before-data-nginx-wski9xf5/nginx.conf`.
