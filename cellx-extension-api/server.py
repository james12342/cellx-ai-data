#!/usr/bin/env python3
import json
import os
import shlex
import subprocess
import sys
import zipfile
from io import BytesIO
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from xml.sax.saxutils import escape as xml_escape


PORT = int(os.getenv("PORT", "3001"))
DB_NAME = os.getenv("DB_NAME", "cellx_base")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
SCRIPT_DIR = os.getenv("SCRIPT_DIR", "/opt/cellx-extension-api/customer-scripts")
SCRIPT_RUNNER_USER = os.getenv("SCRIPT_RUNNER_USER", "cellxrunner")
MAX_SCRIPT_TIMEOUT = int(os.getenv("MAX_SCRIPT_TIMEOUT", "30"))
MAX_SCRIPT_OUTPUT = int(os.getenv("MAX_SCRIPT_OUTPUT", "200000"))


def response(payload, status=200):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return status, data


def normalize_cell(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def excel_col_name(index):
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def xlsx_cell(ref, value):
    value = normalize_cell(value)
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"><v>{value}</v></c>'
    text = xml_escape(str(value))
    return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'


def build_xlsx(rows, sheet_name="Results"):
    rows = rows[:5000]
    columns = []
    seen = set()
    for row in rows:
        if isinstance(row, dict):
            for key in row.keys():
                key = str(key)
                if key not in seen:
                    columns.append(key)
                    seen.add(key)
    if not columns:
        columns = ["value"]

    sheet_rows = []
    header_cells = [xlsx_cell(f"{excel_col_name(index)}1", column) for index, column in enumerate(columns, start=1)]
    sheet_rows.append(f'<row r="1">{"".join(header_cells)}</row>')
    for row_index, row in enumerate(rows, start=2):
        if not isinstance(row, dict):
            row = {"value": row}
        cells = [
            xlsx_cell(f"{excel_col_name(col_index)}{row_index}", row.get(column, ""))
            for col_index, column in enumerate(columns, start=1)
        ]
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>{"".join(sheet_rows)}</sheetData>
</worksheet>'''
    workbook_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="{xml_escape(sheet_name[:31] or "Results")}" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''
    rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    workbook_rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>'''
    content_types_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>'''

    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", rels_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return output.getvalue()


def export_results(payload):
    rows = payload.get("rows") or []
    if not isinstance(rows, list):
        return response({"ok": False, "message": "Export rows must be an array."}, 400)
    if not rows:
        return response({"ok": False, "message": "No rows found to export. Run Connect / Test first."}, 400)
    file_name = os.path.basename(str(payload.get("fileName") or "cellx-workflow-results.xlsx"))
    if not file_name.endswith(".xlsx"):
        file_name = f"{file_name}.xlsx"
    sheet_name = str(payload.get("sheetName") or "Results")
    return 200, build_xlsx(rows, sheet_name), file_name


def db_status():
    if not DB_USER or not DB_PASSWORD:
        return {
            "configured": False,
            "ok": False,
            "message": "DB_USER and DB_PASSWORD are not configured for the extension service.",
        }

    env = os.environ.copy()
    env["MYSQL_PWD"] = DB_PASSWORD
    cmd = [
        "mysql",
        "-h",
        "127.0.0.1",
        "-P",
        "3306",
        "-u",
        DB_USER,
        "-D",
        DB_NAME,
        "-N",
        "-e",
        "SELECT DATABASE(), COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE();",
    ]
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=5, check=False)
    except Exception as exc:
        return {"configured": True, "ok": False, "message": str(exc)}

    if result.returncode != 0:
        return {"configured": True, "ok": False, "message": result.stderr.strip() or "MySQL command failed."}

    parts = result.stdout.strip().split()
    return {
        "configured": True,
        "ok": True,
        "database": parts[0] if parts else DB_NAME,
        "tableCount": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None,
        "message": "Connected to MySQL.",
    }


def mysql_query(sql, timeout=10):
    env = os.environ.copy()
    env["MYSQL_PWD"] = DB_PASSWORD
    cmd = [
        "mysql",
        "-h",
        "127.0.0.1",
        "-P",
        "3306",
        "-u",
        DB_USER,
        "-D",
        DB_NAME,
        "-N",
        "-B",
        "-e",
        sql,
    ]
    return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout, check=False)


def cellx_schema():
    if not DB_USER or not DB_PASSWORD:
        return {"ok": False, "message": "Database is not configured.", "tables": []}, 500

    sql = """
SELECT c.table_name, c.column_name, c.data_type, c.ordinal_position
FROM information_schema.columns c
JOIN information_schema.tables t
  ON c.table_schema = t.table_schema AND c.table_name = t.table_name
WHERE c.table_schema = DATABASE()
  AND t.table_type = 'BASE TABLE'
ORDER BY c.table_name, c.ordinal_position;
"""
    try:
        result = mysql_query(sql)
    except Exception as exc:
        return {"ok": False, "message": str(exc), "tables": []}, 500
    if result.returncode != 0:
        return {"ok": False, "message": result.stderr.strip() or "Could not load CellX schema.", "tables": []}, 500

    tables = {}
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        table_name, column_name, data_type, ordinal = parts[:4]
        table = tables.setdefault(table_name, {"name": table_name, "columns": []})
        table["columns"].append({"name": column_name, "type": data_type, "position": int(ordinal or 0)})

    items = []
    for table in tables.values():
        table["columnCount"] = len(table["columns"])
        items.append(table)
    return {"ok": True, "database": DB_NAME, "tables": items}, 200


def find_rows(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("rows"), list):
            return value["rows"]
        if isinstance(value.get("items"), list):
            return value["items"]
        for child in value.values():
            rows = find_rows(child)
            if rows:
                return rows
    return []


def source_value(row, expression):
    expression = str(expression or "").strip()
    if expression.startswith("{{") and expression.endswith("}}"):
        expression = expression[2:-2].strip()
    for prefix in ("item.", "row.", "previous_step.rows."):
        if expression.startswith(prefix):
            expression = expression[len(prefix):]
            break
    if expression in row:
        return row.get(expression)
    return expression


def parse_field_mapping(mapping_text):
    mappings = []
    for line in str(mapping_text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "<-" in line:
            target, source = line.split("<-", 1)
        elif "=" in line:
            target, source = line.split("=", 1)
        else:
            continue
        target = target.strip()
        source = source.strip()
        if target and source:
            mappings.append({"target": target, "source": source})
    return mappings


def cellx_db_preview(payload):
    settings = payload.get("settings") or {}
    previous_outputs = payload.get("previousOutputs") or []
    previous_payloads = [item.get("output") for item in previous_outputs if isinstance(item, dict)]
    rows = []
    for output in previous_payloads:
        rows = find_rows(output)
        if rows:
            break

    mappings = parse_field_mapping(settings.get("fieldMapping"))
    preview_rows = []
    for row in rows[:5]:
        if not isinstance(row, dict):
            continue
        preview_rows.append({item["target"]: source_value(row, item["source"]) for item in mappings})

    operation = settings.get("operation") or "query"
    table = settings.get("tableName") or "selected table"
    safety = settings.get("safetyMode") or "read_only"
    return {
        "ok": True,
        "status": "success",
        "message": f"Prepared {len(rows)} source rows for CellX {operation} into {table}. Safety mode: {safety}.",
        "input": {
            "operation": operation,
            "tableName": table,
            "inputPayload": settings.get("inputPayload") or "{{previous_step.rows}}",
            "sourceRows": len(rows),
            "mappingCount": len(mappings),
            "safetyMode": safety,
        },
        "output": {
            "ok": True,
            "mode": "preview",
            "operation": operation,
            "tableName": table,
            "sourceRows": len(rows),
            "mapping": mappings,
            "previewRows": preview_rows,
            "note": "Preview only. Enable approved_write later to execute real inserts/updates.",
        },
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }, 200


def first_previous_output(payload):
    previous_outputs = payload.get("previousOutputs") or []
    for item in previous_outputs:
        if isinstance(item, dict) and item.get("output") is not None:
            return item.get("output")
    return {}


def resolve_json_path(root, expression):
    expression = str(expression or "").strip()
    if expression.startswith("{{") and expression.endswith("}}"):
        expression = expression[2:-2].strip()
    if not expression:
        return None

    current = root
    parts = [part for part in expression.split(".") if part]
    for part in parts:
        if part in ("previous_step", "previous"):
            continue
        if part == "length":
            return len(current) if isinstance(current, (list, dict, str)) else 0
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except Exception:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def select_transform_source(previous_output, source_path):
    if not source_path or source_path == "previous_step":
        return previous_output
    source = resolve_json_path(previous_output, source_path)
    return source if source is not None else previous_output


def json_transform_preview(payload):
    settings = payload.get("settings") or {}
    previous_output = first_previous_output(payload)
    source_path = settings.get("sourcePath") or "previous_step"
    source = select_transform_source(previous_output, source_path)
    mapping_text = settings.get("transformMapping") or ""
    mappings = parse_field_mapping(mapping_text)

    mapped = {}
    for item in mappings:
        value = resolve_json_path(source, item["source"])
        if value is None and isinstance(source, dict) and "result" in source:
            value = resolve_json_path(source.get("result"), item["source"])
        mapped[item["target"]] = value

    output_mode = settings.get("outputMode") or "object"
    output = {
        "ok": True,
        "mode": "json_transform",
        "sourcePath": source_path,
        "mapping": mappings,
        "row": mapped,
    }
    if output_mode == "rows":
        output["rows"] = [mapped]
    else:
        output["result"] = mapped

    return {
        "ok": True,
        "status": "success",
        "message": f"Transformed previous output into {len(mapped)} field(s).",
        "input": {
            "sourcePath": source_path,
            "mappingCount": len(mappings),
            "outputMode": output_mode,
        },
        "output": output,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }, 200


def safe_script_path(script_name):
    name = os.path.basename(str(script_name or "").strip())
    if not name or name != str(script_name or "").strip():
        raise ValueError("Choose a script from the approved script folder.")
    if not name.endswith((".py", ".js", ".sh")):
        raise ValueError("Only .py, .js, and .sh scripts are allowed.")
    base = os.path.realpath(SCRIPT_DIR)
    candidate = os.path.realpath(os.path.join(base, name))
    if not candidate.startswith(base + os.sep):
        raise ValueError("Script path is outside the approved script folder.")
    if not os.path.isfile(candidate):
        raise FileNotFoundError(f"Script not found: {name}")
    return candidate


def script_command(script_path, args_text=""):
    extra_args = shlex.split(str(args_text or ""))[:10]
    if script_path.endswith(".py"):
        return [sys.executable, script_path, *extra_args]
    if script_path.endswith(".js"):
        return ["node", script_path, *extra_args]
    return ["bash", script_path, *extra_args]


def script_runner_preexec():
    if os.name != "posix" or not SCRIPT_RUNNER_USER:
        return None

    import pwd

    runner = pwd.getpwnam(SCRIPT_RUNNER_USER)

    def demote():
        os.setgroups([])
        os.setgid(runner.pw_gid)
        os.setuid(runner.pw_uid)

    return demote


def script_runner_env():
    return {
        "PATH": os.getenv("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
        "PYTHONIOENCODING": "utf-8",
    }


def run_customer_script(payload):
    settings = payload.get("settings") or {}
    script_name = settings.get("scriptName") or payload.get("scriptName")
    timeout_raw = settings.get("timeout") or payload.get("timeout") or 20
    try:
        timeout = max(1, min(MAX_SCRIPT_TIMEOUT, int(float(timeout_raw))))
    except Exception:
        timeout = 20

    input_json = settings.get("inputJson") or payload.get("input") or "{}"
    if isinstance(input_json, str):
        try:
            input_payload = json.loads(input_json or "{}")
        except Exception as exc:
            return {
                "ok": False,
                "status": "error",
                "message": f"Input JSON is invalid: {exc}",
                "input": input_json,
            }, 400
    else:
        input_payload = input_json

    try:
        script_path = safe_script_path(script_name)
    except Exception as exc:
        return {
            "ok": False,
            "status": "error",
            "message": str(exc),
            "input": input_payload,
        }, 400

    started = datetime.now(timezone.utc)
    try:
        result = subprocess.run(
            script_command(script_path, settings.get("args", "")),
            input=json.dumps(input_payload, ensure_ascii=False),
            cwd=SCRIPT_DIR,
            env=script_runner_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            preexec_fn=script_runner_preexec(),
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "status": "error",
            "message": f"{script_name} timed out after {timeout} seconds.",
            "input": input_payload,
        }, 408
    except Exception as exc:
        return {
            "ok": False,
            "status": "error",
            "message": str(exc),
            "input": input_payload,
        }, 500

    stdout = (result.stdout or "")[:MAX_SCRIPT_OUTPUT]
    stderr = (result.stderr or "")[:MAX_SCRIPT_OUTPUT]
    parsed = None
    if stdout.strip():
        try:
            parsed = json.loads(stdout)
        except Exception:
            parsed = None

    ok = result.returncode == 0
    return {
        "ok": ok,
        "status": "success" if ok else "error",
        "message": f"{script_name} completed." if ok else f"{script_name} exited with code {result.returncode}.",
        "input": {
            "scriptName": script_name,
            "payload": input_payload,
            "timeout": timeout,
        },
        "output": parsed or {
            "stdout": stdout,
            "stderr": stderr,
            "exitCode": result.returncode,
        },
        "stderr": stderr,
        "exitCode": result.returncode,
        "startedAt": started.isoformat(),
        "finishedAt": datetime.now(timezone.utc).isoformat(),
    }, 200 if ok else 500


def integration_test(payload):
    node_name = payload.get("nodeName") or "Integration"
    node_type = payload.get("nodeType") or ""
    settings = payload.get("settings") or {}
    required = payload.get("required") or []
    missing = [field for field in required if not str(settings.get(field, "")).strip()]

    if missing:
        return {
            "ok": False,
            "status": "error",
            "message": f"{node_name} is missing required setup fields.",
            "missing": missing,
        }, 400

    if node_type == "script" or settings.get("scriptName"):
        return run_customer_script(payload)

    if node_type in ("condition", "control"):
        return {
            "ok": True,
            "status": "success",
            "message": f"{node_name} logic is configured and ready for workflow routing.",
            "checkedAt": datetime.now(timezone.utc).isoformat(),
        }, 200

    if node_type == "cellx-db":
        return cellx_db_preview(payload)

    if node_name == "JSON Transform" or "json-transform" in str(payload.get("action") or ""):
        return json_transform_preview(payload)

    if settings.get("authMode") == "manual_web_handoff":
        return {
            "ok": True,
            "status": "manual",
            "message": f"{node_name} is ready for manual web handoff. The operator signs in to the AI website, runs the generated prompt, then pastes the result into the next step.",
            "checkedAt": datetime.now(timezone.utc).isoformat(),
        }, 200

    if settings.get("authMode") == "bring_your_own_api_key":
        return {
            "ok": True,
            "status": "success",
            "message": f"{node_name} is ready to use the user's own API key. Usage is billed by that provider account.",
            "checkedAt": datetime.now(timezone.utc).isoformat(),
        }, 200

    if settings.get("authMode") == "platform_api_key":
        return {
            "ok": True,
            "status": "success",
            "message": f"{node_name} is ready to use a backend-managed platform secret.",
            "checkedAt": datetime.now(timezone.utc).isoformat(),
        }, 200

    # This endpoint provides the safe connection-test contract. Provider SDK
    # handshakes can be added behind this shape without changing the designer.
    return {
        "ok": True,
        "status": "success",
        "message": f"{node_name} setup looks ready. Required credentials were provided.",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }, 200


class Handler(BaseHTTPRequestHandler):
    server_version = "CellXExtensionAPI/0.1"

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def do_OPTIONS(self):
        self.send_response(204)
        self._headers()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/health":
            status, data = response(
                {
                    "ok": True,
                    "service": "cellx-extension-api",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "version": "0.1.0",
                }
            )
        elif path == "/db/status":
            status, data = response(db_status())
        elif path == "/cellx-db/schema":
            body, status = cellx_schema()
            status, data = response(body, status)
        elif path == "/integrations":
            status, data = response(
                {
                    "items": [
                        {"key": "fedex", "name": "FedEx", "status": "planned", "nextStep": "Create OAuth credentials and rate/label endpoints."},
                        {"key": "ups", "name": "UPS", "status": "planned", "nextStep": "Create client credentials and shipment tracking sync."},
                        {"key": "amazon", "name": "Amazon SP-API", "status": "planned", "nextStep": "Register app, store refresh token, sync orders."},
                        {"key": "openai", "name": "AI Workflow Agent", "status": "prototype", "nextStep": "Define workflow tables and user API-key policy."},
                    ]
                }
            )
        elif path == "/workflows":
            status, data = response(
                {
                    "items": [
                        {"name": "Order risk review", "trigger": "order_created", "action": "Add tag + route to review folder"},
                        {"name": "Shipment tracking sync", "trigger": "tracking_created", "action": "Poll carrier and update order history"},
                        {"name": "AI field builder", "trigger": "admin_prompt", "action": "Suggest page fields and import mappings"},
                    ]
                }
            )
        elif path == "/scripts":
            try:
                scripts = sorted(
                    name for name in os.listdir(SCRIPT_DIR)
                    if name.endswith((".py", ".js", ".sh")) and os.path.isfile(os.path.join(SCRIPT_DIR, name))
                )
                status, data = response({"ok": True, "scriptDir": SCRIPT_DIR, "items": scripts})
            except Exception as exc:
                status, data = response({"ok": False, "message": str(exc), "items": []}, 500)
        else:
            status, data = response({"ok": False, "message": "Not found"}, 404)

        self.send_response(status)
        self._headers()
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            payload = {}

        if path == "/integrations/test":
            body, status = integration_test(payload)
            status, data = response(body, status)
        elif path == "/scripts/run":
            body, status = run_customer_script(payload)
            status, data = response(body, status)
        elif path == "/results/export":
            export = export_results(payload)
            if len(export) == 3:
                status, data, file_name = export
                self.send_response(status)
                self._headers(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    f'attachment; filename="{file_name}"',
                )
                self.end_headers()
                self.wfile.write(data)
                return
            status, data = export
        else:
            status, data = response({"ok": False, "message": "Not found"}, 404)

        self.send_response(status)
        self._headers()
        self.end_headers()
        self.wfile.write(data)

    def _headers(self, content_type="application/json; charset=utf-8", content_disposition=None):
        self.send_header("Content-Type", content_type)
        if content_disposition:
            self.send_header("Content-Disposition", content_disposition)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")


if __name__ == "__main__":
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"cellx-extension-api listening on 127.0.0.1:{PORT}", flush=True)
    httpd.serve_forever()
