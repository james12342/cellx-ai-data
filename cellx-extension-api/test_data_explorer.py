import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import data_explorer as explorer


spec = importlib.util.spec_from_file_location("explorer_test_server", Path(__file__).with_name("server.py"))
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def column(name, kind="varchar", table="orders", primary=False):
    return {"table_name": table, "name": name, "type": kind,
            "nullable": "YES", "column_key": "PRI" if primary else "", "max_length": 64}


class ExplorerTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.cursor = self.db.cursor.return_value.__enter__.return_value
        self.cursor.fetchmany.side_effect = [
            [column("id", "int", primary=True), column("status"), column("email"),
             column("api_key"), column("payload", "json"), column("detail", "text")], [],
            [{"id": 1, "status": "ready", "email": None, "api_key": None, "payload": None, "detail": None}]]
        self.connect = MagicMock()
        self.connect.return_value.__enter__.return_value = self.db
        self.token = patch.object(server, "WORKFLOW_MANAGEMENT_TOKEN", "test-token")
        self.token.start()
        self.addCleanup(self.token.stop)

    def request(self, operation="rows", query=None, headers=None, method="GET", registry=None):
        return explorer.handle_request(method, "/data-explorer/" + operation,
            {"X-Workflow-Admin-Token": "test-token"} if headers is None else headers,
            {"table": ["orders"]} if query is None else query,
            authorize=server.workflow_management_auth, connect=self.connect,
            registry_path=registry, allowed_origin="https://app.cellaidata.com")

    def test_auth_precedes_all_database_access(self):
        for method in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"):
            for headers in ({}, {"X-Workflow-Admin-Token": "wrong"},
                            {"X-Workflow-Admin-Token": "\u2603"},
                            {"Authorization": "Bearer test-token", "role": "admin"}):
                with self.subTest(method=method, headers=headers):
                    self.assertEqual(self.request(headers=headers, method=method)[1], 401)
        self.connect.assert_not_called()

    def test_query_token_and_identity_claims_cannot_authorize(self):
        result = self.request(headers={}, query={"adminToken": ["test-token"], "company": ["admin"], "email": ["a@b"], "role": ["admin"]})
        self.assertEqual(result[1], 401)
        self.connect.assert_not_called()

    def test_unconfigured_token_denies(self):
        with patch.object(server, "WORKFLOW_MANAGEMENT_TOKEN", ""):
            self.assertEqual(self.request()[1], 403)
        self.connect.assert_not_called()

    def test_foreign_origin_and_mutations_denied(self):
        self.assertEqual(self.request(headers={"X-Workflow-Admin-Token": "test-token", "Origin": "https://evil.example"})[1], 403)
        for method in ("POST", "DELETE", "PUT", "PATCH", "HEAD"):
            self.assertEqual(self.request(method=method)[1], 405)
        self.connect.assert_not_called()

    def test_bound_filters_search_and_paging(self):
        malicious = "ready' OR 1=1 --"
        body, status = self.request(query={"table": ["orders"], "page_size": ["1"],
            "search": [malicious], "filters": [json.dumps({"status": malicious})]})
        self.assertEqual(status, 200)
        sql, params = self.cursor.execute.call_args.args
        self.assertNotIn(malicious, sql)
        self.assertEqual(params, (malicious, malicious, 2, 0))
        self.assertIn("NULL AS `email`", sql)
        self.assertIn("NULL AS `api_key`", sql)
        self.assertIn("NULL AS `payload`", sql)
        self.assertEqual(body["rows"][0]["email"], "[REDACTED]")
        self.assertEqual(body["rows"][0]["detail"], "[REDACTED]")
        self.assertFalse(body["has_more"])
        self.assertTrue(all(call.args[0].startswith("SELECT ") for call in self.cursor.execute.call_args_list))

    def test_invalid_and_sensitive_identifiers(self):
        for query, code in [({"table": ["orders; DROP TABLE orders"]}, 400),
                            ({"table": ["missing"]}, 404),
                            ({"table": ["orders"], "sort": ["email"]}, 403),
                            ({"table": ["orders"], "sort": ["unknown"]}, 400),
                            ({"table": ["orders"], "filters": ['{"api_key":"x"}']}, 403),
                            ({"table": ["orders"], "direction": ["asc;DELETE"]}, 400)]:
            self.setUpCursor()
            self.assertEqual(self.request(query=query)[1], code)
            self.assertEqual(self.cursor.execute.call_count, 2)

    def setUpCursor(self):
        self.cursor.reset_mock()
        self.cursor.fetchmany.side_effect = [[column("id", "int", primary=True), column("email"), column("api_key")], []]

    def test_bounded_and_strict_inputs(self):
        for extra in ({"page": ["0"]}, {"page_size": ["101"]}, {"page": ["1000"]},
                      {"page": ["1", "2"]}, {"company": ["x"]}, {"search": ["x" * 129]},
                      {"filters": ["[]"]}, {"filters": ['{"id":NaN}']},
                      {"filters": ['{"id":{"op":"sql"}}']}, {"filters": ["x" * 4097]}):
            self.setUpCursor()
            with self.subTest(extra=extra):
                self.assertEqual(self.request(query={"table": ["orders"], **extra})[1], 400)

    def test_registry_absence_never_creates_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "absent.sqlite3"
            self.assertEqual(explorer.registry_bindings(path), ([], False))
            self.assertFalse(path.exists())

    def test_real_and_planned_remain_distinct(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "registry.sqlite3"
            with sqlite3.connect(path) as db:
                db.executescript("""PRAGMA application_id=1128354642;
                    CREATE TABLE tenants(id,name);
                    INSERT INTO tenants VALUES ('co','Company');
                    CREATE TABLE table_registry(id,tenant_id,physical_name);
                    CREATE TABLE table_use(table_id,tenant_id,agent_id,state);
                    CREATE TABLE agents(id,tenant_id,name,state);
                    INSERT INTO table_registry VALUES ('t','co','orders'),('p','co','not_created');
                    INSERT INTO table_use VALUES ('t','co','a','active');
                    INSERT INTO agents VALUES ('a','co','Agent','active');""")
            db.close()
            before = path.read_bytes()
            body, status = self.request("catalog", {}, registry=path)
            self.assertEqual(status, 200)
            self.assertEqual(body["tables"][0]["association"], "registry_planned")
            self.assertEqual(body["tables"][0]["agents"][0]["id"], "a")
            self.assertEqual(body["tables"][0]["company_id"], "co")
            self.assertEqual(body["companies"], [{"id": "co", "name": "Company"}])
            self.assertEqual(body["agents"][0]["company_id"], "co")
            planned = {t["name"]: t for t in body["planned_tables"]}
            self.assertFalse(planned["not_created"]["physical_exists"])
            self.assertTrue(planned["orders"]["physical_exists"])
            self.assertTrue(all(t["state"] == "planned" for t in planned.values()))
            self.assertEqual(path.read_bytes(), before)

    def test_unknown_registry_is_not_opened_for_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "unknown.sqlite3"
            path.write_bytes(b"not a database")
            self.assertEqual(explorer.registry_bindings(path), ([], False))
            self.assertEqual(path.read_bytes(), b"not a database")

    def test_driver_transaction_and_cleanup(self):
        driver = MagicMock()
        db = driver.connect.return_value
        with patch.dict(sys.modules, {"pymysql": driver}):
            with self.assertRaises(RuntimeError):
                with explorer.mysql_connection("cellx_base", "user", "private"):
                    raise RuntimeError("test")
        self.assertEqual(driver.connect.call_args.kwargs["host"], "127.0.0.1")
        self.assertEqual(driver.connect.call_args.kwargs["port"], 3306)
        db.cursor.return_value.__enter__.return_value.execute.assert_called_once_with("START TRANSACTION READ ONLY")
        db.rollback.assert_called_once()
        db.close.assert_called_once()

    def test_missing_driver_and_sanitized_database_failure(self):
        with patch.dict(sys.modules, {"pymysql": None}):
            with self.assertRaises(explorer.ExplorerError) as error:
                with explorer.mysql_connection("cellx_base", "user", "private"):
                    pass
        self.assertEqual(error.exception.code, "database_driver_unavailable")
        self.connect.side_effect = RuntimeError("password=private ROW DATA")
        body, status = self.request()
        self.assertEqual(status, 503)
        self.assertEqual(body, {"ok": False, "code": "database_unavailable"})

    def test_has_more_and_null_filter(self):
        self.cursor.fetchmany.side_effect = [[column("id", "int", primary=True)], [], [{"id": 1}, {"id": 2}]]
        body, status = self.request(query={"table": ["orders"], "page_size": ["1"], "filters": ['{"id":null}']})
        self.assertEqual(status, 200)
        self.assertTrue(body["has_more"])
        self.assertEqual(len(body["rows"]), 1)
        self.assertIn("`id` IS NULL", self.cursor.execute.call_args.args[0])

    def test_server_routes_no_store_and_auth_before_body(self):
        for path in ("/data-explorer/rows", "/ext-api/data-explorer/rows"):
            handler = object.__new__(server.Handler)
            handler.path = path + "?table=orders"
            handler.headers = {}
            handler.wfile = io.BytesIO()
            handler.rfile = MagicMock()
            handler.send_response = MagicMock()
            handler.send_header = MagicMock()
            handler.end_headers = MagicMock()
            handler.serve_ui_static = MagicMock()
            handler.do_GET()
            handler.send_response.assert_called_with(401)
            handler.send_header.assert_any_call("Cache-Control", "no-store")
            handler.serve_ui_static.assert_not_called()
            handler.do_POST()
            handler.rfile.read.assert_not_called()

    def test_explorer_query_values_are_not_logged(self):
        handler = object.__new__(server.Handler)
        handler.path = "/ext-api/data-explorer/rows?adminToken=private&search=personal"
        with patch("builtins.print") as output:
            handler.log_message("%s", handler.path)
        output.assert_not_called()

    def test_unlinked_and_fully_masked_table_metadata(self):
        self.cursor.fetchmany.side_effect = [[column("email")], [], [{"email": None}]]
        body, status = self.request("table")
        self.assertEqual(status, 200)
        self.assertIsNone(body["table"]["company_id"])
        self.assertEqual(body["table"]["association"], "unlinked")
        self.assertTrue(body["table"]["all_columns_masked"])

    def test_unknown_text_and_credential_aliases_masked_in_database(self):
        names = ("pwd", "access_key", "connection_string", "pin", "custom_value")
        self.cursor.fetchmany.side_effect = [[column(name) for name in names], [], [{name: None for name in names}]]
        body, status = self.request()
        self.assertEqual(status, 200)
        self.assertTrue(all(c["masked"] for c in body["columns"]))
        self.assertTrue(all(v == "[REDACTED]" for v in body["rows"][0].values()))
        sql = self.cursor.execute.call_args.args[0]
        for name in names:
            self.assertIn("NULL AS `" + name + "`", sql)
            for option in ({"sort": [name]}, {"filters": [json.dumps({name: "value"})]}):
                self.cursor.fetchmany.side_effect = [[column(name)], []]
                self.assertEqual(self.request(query={"table": ["orders"], **option})[1], 403)
        self.cursor.fetchmany.side_effect = [[column(name) for name in names], []]
        self.assertEqual(self.request(query={"table": ["orders"], "search": ["value"]})[1], 400)

    def test_system_tables_default_mask_even_operational_columns(self):
        self.cursor.fetchmany.side_effect = [[column("status", table="users"), column("id", "bigint", table="users")], []]
        body, status = self.request("table", {"table": ["users"]})
        self.assertEqual(status, 200)
        self.assertTrue(body["table"]["all_columns_masked"])

    def test_large_integer_serialization_and_exact_string_filter(self):
        value = 9007199254740993
        self.cursor.fetchmany.side_effect = [[column("id", "bigint", primary=True)], [], [{"id": value}]]
        body, status = self.request(query={"table": ["orders"], "filters": [json.dumps({"id": str(value)})]})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(json.dumps(body))["rows"][0]["id"], str(value))
        self.assertEqual(self.cursor.execute.call_args.args[1][0], str(value))
        self.assertIn("`id` = CAST(%s AS DECIMAL(65,0))", self.cursor.execute.call_args.args[0])
        self.assertEqual(explorer.value_json(-value), str(-value))
        self.assertEqual(explorer.value_json(9007199254740991), 9007199254740991)

    def test_registry_query_has_progress_budget(self):
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = [1128354642]
        db.execute.return_value.fetchall.return_value = []
        with patch.object(Path, "is_file", return_value=True), patch.object(explorer.sqlite3, "connect", return_value=db):
            self.assertEqual(explorer.registry_bindings("unused.sqlite3"), ([], True))
        callback, interval = db.set_progress_handler.call_args.args
        self.assertEqual(interval, 1000)
        with patch.object(explorer, "monotonic", return_value=float("inf")):
            self.assertEqual(callback(), 1)
        db.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
