import copy
import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server
from workflow_scheduler import WorkflowScheduler, daily_settings, next_daily, normalized_workflow, utc_now


NOW = datetime(2026, 9, 14, 12, 59, 50, tzinfo=timezone.utc)


def fixture():
    return {
        "id": "daily-test", "name": "Daily test",
        "nodes": [
            {"id": "start", "type": "trigger", "name": "Daily Schedule", "action": "cron", "integrationSettings": {"schedule": "0 6 * * *", "timezone": "America/Los_Angeles", "scheduleEnabled": "true"}},
            {"id": "fetch", "type": "script", "name": "Fetch", "action": "/ext-api/scripts/run", "integrationSettings": {"scriptName": "fixture.py", "inputJson": "{}"}},
            {"id": "write", "type": "cellx-db", "name": "Import", "action": "/ext-api/cellx-db/bulk-import", "integrationSettings": {"operation": "bulk_import", "safetyMode": "approved_write"}},
            {"id": "summary", "type": "tool", "name": "Summary", "action": "/ext-api/tools/json-transform", "integrationSettings": {"sourcePath": "previous_step", "transformMapping": "orders <- {{row_count}}", "outputMode": "rows"}},
            {"id": "log", "type": "log", "name": "Log", "action": "cx_workflow_log", "integrationSettings": {}},
        ],
        "links": [{"from": "start", "to": "fetch"}, {"from": "fetch", "to": "write"}, {"from": "fetch", "to": "summary"}, {"from": "write", "to": "log"}, {"from": "summary", "to": "log"}],
    }


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.calls = []
        self.scheduler = WorkflowScheduler(str(Path(self.temp.name) / "schedules.db"), self.dispatch)

    def dispatch(self, payload):
        self.calls.append(payload)
        if payload["nodeType"] == "script":
            return {"ok": True, "status": "success", "output": {"ok": True, "rows": [{"order_id": 1}, {"order_id": 2}], "row_count": 2}}, 200
        if payload["nodeType"] == "cellx-db":
            rows = payload["previousOutputs"][0]["output"]["rows"]
            return {"ok": True, "output": {"writtenRows": len(rows)}}, 200
        return server.integration_test(payload)

    def test_due_full_graph_and_once_only(self):
        self.scheduler.save(fixture(), NOW)
        self.assertEqual(self.scheduler.tick(NOW), 0)
        self.assertEqual(self.scheduler.tick(NOW + timedelta(seconds=11)), 1)
        self.assertEqual(self.scheduler.tick(NOW + timedelta(seconds=35)), 0)
        record = self.scheduler.status("daily-test")["runs"][0]
        self.assertEqual(record["status"], "success")
        self.assertEqual(record["source"], "scheduled")
        self.assertEqual(len(record["steps"]), 5)
        self.assertEqual(record["steps"][2]["row_count"], 2)
        self.assertEqual(self.calls[2]["previousOutputs"][0]["node"], "Fetch")

    def test_manual_and_scheduled_share_dispatch(self):
        result = self.scheduler.run_manual(fixture())
        self.assertTrue(result["ok"])
        self.assertEqual(result["results"][3]["output"]["rows"], [{"orders": 2}])
        self.assertEqual(result["results"][-1]["output"]["logged"], True)
        manual_types = [item["nodeType"] for item in self.calls]
        self.calls.clear()
        self.scheduler.save(fixture(), NOW)
        self.scheduler.tick(NOW + timedelta(minutes=1))
        self.assertEqual(manual_types, [item["nodeType"] for item in self.calls])

    def test_failure_skips_downstream(self):
        self.scheduler.dispatch = lambda payload: ({"ok": False, "output": {"ok": False}}, 502)
        result = self.scheduler.run_manual(fixture())
        self.assertFalse(result["ok"])
        self.assertEqual([item["status"] for item in result["results"]], ["success", "error", "skipped", "skipped", "skipped"])

    def test_disabled_and_resave_does_not_postpone_due(self):
        workflow = fixture()
        saved = self.scheduler.save(workflow, NOW)
        resaved = self.scheduler.save(workflow, NOW + timedelta(minutes=1))
        self.assertEqual(saved["nextRun"], resaved["nextRun"])
        workflow["nodes"][0]["integrationSettings"]["scheduleEnabled"] = "false"
        self.scheduler.save(workflow, NOW + timedelta(minutes=1))
        self.assertEqual(self.scheduler.tick(NOW + timedelta(hours=3)), 0)

    def test_persistence_and_missed_run_catchup(self):
        self.scheduler.save(fixture(), NOW)
        reopened = WorkflowScheduler(self.scheduler.path, self.dispatch)
        self.assertEqual(reopened.tick(NOW + timedelta(days=3)), 1)
        self.assertEqual(reopened.tick(NOW + timedelta(days=3)), 0)
        self.assertGreater(datetime.fromisoformat(reopened.status("daily-test")["nextRun"]), NOW + timedelta(days=3))

    def test_overlapping_claim_and_duplicate_date(self):
        self.scheduler.save(fixture(), NOW)
        due = NOW + timedelta(minutes=1)
        claim = self.scheduler.claim("daily-test", due)
        self.assertIsNotNone(claim)
        self.assertIsNone(self.scheduler.claim("daily-test", due, "manual", fixture()))
        self.scheduler.execute(*claim, "scheduled")
        with self.scheduler.connect() as db:
            db.execute("UPDATE schedules SET next_run=?", ((NOW + timedelta(seconds=10)).isoformat(),))
        self.assertIsNone(self.scheduler.claim("daily-test", due))

    def test_configuration_validation_and_no_secrets_in_status(self):
        workflow = fixture()
        settings = workflow["nodes"][1]["integrationSettings"]
        settings["scriptName"] = "orderdesk_orders_to_db.py"
        with patch.dict(os.environ, {"ORDERDESK_STORE_ID": "", "ORDERDESK_API_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "ORDERDESK"):
                self.scheduler.save(workflow, NOW)
        settings.update(orderdeskStoreId="fixture-store", orderdeskApiKey="fixture-secret")
        workflow["nodes"][1]["testResult"] = {"private": "customer data"}
        self.scheduler.save(workflow, NOW)
        self.assertNotIn("fixture-secret", json.dumps(self.scheduler.status(workflow["id"])))
        with self.scheduler.connect() as db:
            self.assertNotIn("customer data", db.execute("SELECT workflow FROM schedules").fetchone()[0])
        if os.name == "posix":
            self.assertEqual(os.stat(self.scheduler.path).st_mode & 0o777, 0o600)

    def test_daily_timezone_dst_and_validation(self):
        workflow = fixture()
        self.assertEqual(next_daily(workflow, NOW).isoformat(), "2026-09-14T13:00:00+00:00")
        settings = workflow["nodes"][0]["integrationSettings"]
        settings["schedule"] = "30 1 * * *"
        first_fold = datetime(2026, 11, 1, 8, 30, tzinfo=timezone.utc)
        self.assertEqual(next_daily(workflow, first_fold).day, 2)
        settings["schedule"] = "30 2 * * *"
        spring = datetime(2026, 3, 8, 9, 0, tzinfo=timezone.utc)
        self.assertEqual(next_daily(workflow, spring).isoformat(), "2026-03-08T10:30:00+00:00")
        settings["schedule"] = "* * * * *"
        with self.assertRaises(ValueError):
            daily_settings(workflow)
        settings["schedule"] = "0 6 * * *"
        settings["timezone"] = "Not/A_Timezone"
        with self.assertRaises(ValueError):
            daily_settings(workflow)

    def test_reject_cycles_missing_nodes_and_unsupported_actions(self):
        for change in ["cycle", "missing", "unsupported"]:
            workflow = fixture()
            if change == "cycle":
                workflow["links"].append({"from": "log", "to": "fetch"})
            elif change == "missing":
                workflow["links"][0]["to"] = "missing"
            else:
                workflow["nodes"][1]["type"] = "condition"
            with self.assertRaises(ValueError):
                normalized_workflow(workflow)

    def test_actual_worker_triggers_without_browser(self):
        self.scheduler.save(fixture(), utc_now() - timedelta(days=2))
        self.scheduler.start()
        try:
            self.scheduler.thread.join(timeout=.3)
            with self.scheduler.connect() as db:
                rows = db.execute("SELECT status FROM runs").fetchall()
            self.assertTrue(self.scheduler.health()["running"])
            self.assertIsNotNone(self.scheduler.health()["lastPoll"])
            self.assertEqual([row["status"] for row in rows], ["success"])
        finally:
            self.scheduler.stop_event.set()
            self.scheduler.thread.join(timeout=5)
            if self.scheduler.process_lock:
                self.scheduler.process_lock.close()

    def test_api_auth_save_status_and_manual_test(self):
        with patch.object(server, "_workflow_scheduler", self.scheduler), patch.object(server, "WORKFLOW_MANAGEMENT_TOKEN", "fixture-admin"):
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{httpd.server_port}"
                body = json.dumps({"workflow": fixture()}).encode()
                with self.assertRaises(HTTPError) as caught:
                    urlopen(Request(base + "/workflow-schedules/save", data=body), timeout=5)
                self.assertEqual(caught.exception.code, 401)
                headers = {"Content-Type": "application/json", "X-Workflow-Admin-Token": "fixture-admin"}
                with urlopen(Request(base + "/workflow-schedules/save", data=body, headers=headers), timeout=5) as response:
                    self.assertTrue(json.load(response)["schedule"]["enabled"])
                with urlopen(Request(base + "/workflow-schedules?id=daily-test", headers=headers), timeout=5) as response:
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertTrue(json.load(response)["schedule"]["saved"])
                with urlopen(Request(base + "/workflows/run", data=body, headers=headers), timeout=5) as response:
                    self.assertTrue(json.load(response)["ok"])
                trigger = fixture()["nodes"][0]
                payload = {"nodeType": "trigger", "nodeName": trigger["name"], "action": "cron", "settings": trigger["integrationSettings"]}
                with urlopen(Request(base + "/integrations/test", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}), timeout=5) as response:
                    self.assertFalse(json.load(response)["output"]["scheduledRun"])
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)

    def test_large_script_json_is_not_truncated_before_import(self):
        payload = {"ok": True, "rows": [{"text": "x" * 1000, "rank": i} for i in range(300)]}
        completed = SimpleNamespace(stdout=json.dumps(payload), stderr="", returncode=0)
        with patch.object(server, "safe_script_path", return_value="fixture.py"), patch.object(server, "script_runner_preexec", return_value=None), patch.object(server.subprocess, "run", return_value=completed):
            result, status = server.run_customer_script({"settings": {"scriptName": "fixture.py", "inputJson": "{}"}})
        self.assertEqual(status, 200)
        self.assertEqual(len(result["output"]["rows"]), 300)

    def test_agent_route_and_legacy_bookmarks(self):
        folder = Path(self.temp.name)
        (folder / "index.html").write_text("<h1>Agent Builder</h1>", encoding="utf-8")
        (folder / "app.js").write_text("console.log('fixture');", encoding="utf-8")
        with patch.object(server, "UI_DIR", str(folder)):
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{httpd.server_port}"
                for path in ("/agent/", "/agent", "/workflow", "/workflow/", "/"):
                    with urlopen(base + path + "?checkout=success&test=1", timeout=5) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIn("/agent/?checkout=success&test=1", response.url)
                        self.assertIn(b"Agent Builder", response.read())
                for path in ("/agent/app.js", "/workflow/app.js"):
                    with urlopen(base + path, timeout=5) as response:
                        self.assertIn("javascript", response.headers["Content-Type"])
                        self.assertIn(b"fixture", response.read())
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
