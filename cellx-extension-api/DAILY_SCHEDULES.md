# Daily schedules

The API starts a daily scheduler thread on boot. It polls every 15 seconds, even
when the browser is closed. `/health` reports its running state and last poll.
`WORKFLOW_SCHEDULER_ENABLED=false` disables the worker.

## Saving a schedule

Select the cron trigger, choose Enabled, enter a daily expression such as
`0 6 * * *` and an IANA timezone such as `America/Los_Angeles`, then Save Draft.
Save Config also updates the active workflow's server schedule. These requests
use the existing workflow-management admin token. The confirmation must say
the schedule was saved on the server and show its next run; a local-only save
or a successful Test Selected does not enable background execution.

OrderDesk credentials must either be included in the saved step configuration
or provided by the API service environment. Missing credentials reject enabling
the schedule. Existing schedules remain unchanged when validation fails.
Credentials are not returned by the status endpoint or recorded in run history.

The old `cellx-orderdesk-daily-sync.timer` used a separate fixed 9 PM schedule and
failed because it lacked credentials. It is disabled after this migration.
Do not re-enable it alongside the new schedule.

## Execution and history

Supported daily graphs contain one cron trigger, scripts, database queries or
approved writes, JSON transforms, and log steps. Unsupported steps and cycles
are rejected rather than silently treated as successful. This version supports
daily `minute hour * * *` expressions, not arbitrary cron intervals.

Run Agent (previously Run Workflow) for supported graphs and scheduled runs share the server executor
and existing integration handlers. Test Selected remains a single-step test.
Steps receive their direct predecessors' outputs. Failed predecessors cause
dependent steps to be skipped. Log steps are recorded in scheduler history,
not the previously simulated `cx_workflow_log` output.

Schedule Status shows the next run, last ten runs and step statuses/counts.
The durable store is `workflow-schedules.sqlite3` beside `server.py`, overrideable
with `WORKFLOW_SCHEDULE_DB`. It is mode 0600 on Linux and excluded from Git.
Back it up as private configuration; it may contain credentials.

Claims are transactional. A workflow cannot overlap itself, and the same daily
slot cannot execute twice. A restart records unfinished runs as interrupted
without retrying their side effects. Missed schedules catch up once on restart;
subsequent missed dates are skipped. Fall-back runs once; a spring-forward gap
moves to the corresponding valid time. Disabling does not cancel an in-flight run.

## Verification

Run `python -m unittest test_workflow_scheduler -v` in this directory.
The browser regression check is `node scripts/test_daily_scheduler_ui.cjs` from
the repository root; it uses fixture credentials and a mocked API.

On AWS, `sudo python3 scripts/smoke_daily_scheduler_aws.py create` schedules an
isolated transform/log test for the next minute. Run `check` for its history,
then `disable`. It uses the service's existing admin token in memory and does
not call external providers or send messages.
