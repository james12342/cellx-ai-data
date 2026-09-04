#!/usr/bin/env python3
import json
import os
import re
import shlex
import smtplib
import subprocess
import sys
import zipfile
from email.message import EmailMessage
from io import BytesIO
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape as xml_escape


PORT = int(os.getenv("PORT", "3001"))
DB_NAME = os.getenv("DB_NAME", "cellx_base")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
SCRIPT_DIR = os.getenv("SCRIPT_DIR", "/opt/cellx-extension-api/customer-scripts")
SCRIPT_RUNNER_USER = os.getenv("SCRIPT_RUNNER_USER", "cellxrunner")
MAX_SCRIPT_TIMEOUT = int(os.getenv("MAX_SCRIPT_TIMEOUT", "30"))
MAX_SCRIPT_OUTPUT = int(os.getenv("MAX_SCRIPT_OUTPUT", "200000"))
MARKETPLACE_STORE = os.getenv("MARKETPLACE_STORE", os.path.join(os.path.dirname(__file__), "marketplace-store.json"))
PLATFORM_COMMISSION_RATE = float(os.getenv("PLATFORM_COMMISSION_RATE", "0.25"))


def response(payload, status=200):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return status, data


def marketplace_store_default():
    return {"templates": [], "purchases": []}


def load_marketplace_store():
    if not os.path.exists(MARKETPLACE_STORE):
        return marketplace_store_default()
    try:
        with open(MARKETPLACE_STORE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return marketplace_store_default()
    if not isinstance(data, dict):
        return marketplace_store_default()
    data.setdefault("templates", [])
    data.setdefault("purchases", [])
    return data


def save_marketplace_store(data):
    folder = os.path.dirname(MARKETPLACE_STORE)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp_path = MARKETPLACE_STORE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, MARKETPLACE_STORE)


def clean_marketplace_text(value, fallback="", limit=300):
    text = str(value or fallback).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def marketplace_templates():
    data = load_marketplace_store()
    templates = sorted(data.get("templates", []), key=lambda item: item.get("createdAt", ""), reverse=True)
    return {
        "ok": True,
        "commissionRate": PLATFORM_COMMISSION_RATE,
        "items": templates,
    }


def create_marketplace_template(payload):
    template = payload.get("template")
    if not isinstance(template, dict) or not isinstance(template.get("nodes"), list) or not isinstance(template.get("links"), list):
        return {"ok": False, "message": "A valid workflow template with nodes and links is required."}, 400

    price = payload.get("price")
    try:
        price = max(0, round(float(price or 0), 2))
    except Exception:
        price = 0

    now = datetime.now(timezone.utc).isoformat()
    item = {
        "id": f"tmpl-{int(datetime.now(timezone.utc).timestamp())}-{abs(hash(json.dumps(template, sort_keys=True, default=str))) % 100000}",
        "name": clean_marketplace_text(payload.get("name") or template.get("name"), "Untitled workflow template", 120),
        "description": clean_marketplace_text(payload.get("description") or template.get("description"), "Reusable workflow template.", 500),
        "category": clean_marketplace_text(payload.get("category"), "Workflow", 80),
        "developerName": clean_marketplace_text(payload.get("developerName"), "Cell AI Data Developer", 120),
        "price": price,
        "currency": "USD",
        "license": clean_marketplace_text(payload.get("license"), "Single business workspace", 120),
        "status": "listed",
        "commissionRate": PLATFORM_COMMISSION_RATE,
        "developerShare": round(price * (1 - PLATFORM_COMMISSION_RATE), 2),
        "platformFee": round(price * PLATFORM_COMMISSION_RATE, 2),
        "sales": 0,
        "createdAt": now,
        "updatedAt": now,
        "template": template,
    }

    data = load_marketplace_store()
    data["templates"].append(item)
    save_marketplace_store(data)
    return {"ok": True, "item": item}, 201


def purchase_marketplace_template(payload):
    template_id = clean_marketplace_text(payload.get("templateId"), "", 120)
    buyer_email = clean_marketplace_text(payload.get("buyerEmail"), "demo-buyer@example.com", 180)
    data = load_marketplace_store()
    template = next((item for item in data.get("templates", []) if item.get("id") == template_id), None)
    if not template:
        return {"ok": False, "message": "Marketplace template not found."}, 404

    price = float(template.get("price") or 0)
    purchase = {
        "id": f"purchase-{int(datetime.now(timezone.utc).timestamp())}-{len(data.get('purchases', [])) + 1}",
        "templateId": template_id,
        "templateName": template.get("name"),
        "buyerEmail": buyer_email,
        "price": price,
        "currency": template.get("currency") or "USD",
        "platformFee": round(price * PLATFORM_COMMISSION_RATE, 2),
        "developerPayout": round(price * (1 - PLATFORM_COMMISSION_RATE), 2),
        "status": "demo_paid" if price else "free_install",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    template["sales"] = int(template.get("sales") or 0) + 1
    template["updatedAt"] = purchase["createdAt"]
    data["purchases"].append(purchase)
    save_marketplace_store(data)
    return {"ok": True, "purchase": purchase, "template": template}, 200


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
SELECT c.table_name, c.column_name, c.data_type, c.ordinal_position, c.character_maximum_length
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
        max_length = parts[4] if len(parts) > 4 and parts[4] else None
        table = tables.setdefault(table_name, {"name": table_name, "columns": []})
        table["columns"].append({
            "name": column_name,
            "type": data_type,
            "position": int(ordinal or 0),
            "maxLength": int(max_length) if str(max_length or "").isdigit() else None,
        })

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


def sql_identifier(name):
    name = str(name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError(f"Unsafe SQL identifier: {name}")
    return f"`{name}`"


def sql_literal(value):
    if value is None or value == "":
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    text = str(value)
    return "'" + text.replace("\\", "\\\\").replace("'", "''") + "'"


def load_cellx_schema_map():
    body, status = cellx_schema()
    if status != 200 or not body.get("ok"):
        raise RuntimeError(body.get("message") or "Could not load CellX schema.")
    return {
        table["name"]: {column["name"]: column for column in table.get("columns", [])}
        for table in body.get("tables", [])
    }


def coerce_cellx_value(value, column):
    if value in ("", None):
        return None
    data_type = str((column or {}).get("type") or "").lower()
    if data_type == "date" and isinstance(value, str):
        match = re.match(r"^(\d{4}-\d{2}-\d{2})", value.strip())
        return match.group(1) if match else value
    if data_type in ("datetime", "timestamp") and isinstance(value, str):
        text = value.strip().replace("T", " ").replace("Z", "")
        return text[:19] if re.match(r"^\d{4}-\d{2}-\d{2} ", text) else value
    if data_type in ("bigint", "int", "integer", "smallint", "tinyint"):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
    if data_type in ("double", "float", "decimal"):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    max_length = column.get("maxLength") if isinstance(column, dict) else None
    if max_length and isinstance(value, str) and len(value) > max_length:
        return value[:max_length]
    return value


def mapped_rows_for_cellx(rows, mappings, allowed_columns):
    output_rows = []
    skipped_columns = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = {}
        for mapping in mappings:
            target = mapping["target"]
            if target not in allowed_columns:
                skipped_columns.add(target)
                continue
            item[target] = coerce_cellx_value(source_value(row, mapping["source"]), allowed_columns[target])
        if item:
            output_rows.append(item)
    return output_rows, sorted(skipped_columns)


def add_insert_defaults(row, columns):
    now_columns = {"create_time", "update_time"}
    if "uuid" in columns and "uuid" not in row:
        row["uuid"] = {"sql": "UUID()"}
    if "del_flag" in columns and "del_flag" not in row:
        row["del_flag"] = "0"
    if "dept_id" in columns and "dept_id" not in row:
        row["dept_id"] = 0
    if "owner" in columns and "owner" not in row:
        row["owner"] = "workflow"
    if "create_by" in columns and "create_by" not in row:
        row["create_by"] = "workflow"
    if "update_by" in columns and "update_by" not in row:
        row["update_by"] = "workflow"
    for column in now_columns:
        if column in columns and column not in row:
            row[column] = {"sql": "NOW()"}
    return row


def add_update_defaults(row, columns):
    if "update_by" in columns:
        row["update_by"] = "workflow"
    if "update_time" in columns:
        row["update_time"] = {"sql": "NOW()"}
    return row


def sql_value(value):
    if isinstance(value, dict) and set(value.keys()) == {"sql"}:
        return value["sql"]
    return sql_literal(value)


def build_insert_if_missing_sql(table, row, unique_key=None):
    columns = list(row.keys())
    column_sql = ", ".join(sql_identifier(column) for column in columns)
    value_sql = ", ".join(sql_value(row[column]) for column in columns)
    base = f"INSERT INTO {sql_identifier(table)} ({column_sql}) SELECT {value_sql}"
    if unique_key and row.get(unique_key) not in (None, ""):
        return f"{base} WHERE NOT EXISTS (SELECT 1 FROM {sql_identifier(table)} WHERE {sql_identifier(unique_key)} = {sql_literal(row.get(unique_key))} LIMIT 1)"
    return f"INSERT INTO {sql_identifier(table)} ({column_sql}) VALUES ({value_sql})"


def build_update_sql(table, row, unique_key):
    update_row = {key: value for key, value in row.items() if key != unique_key}
    if not update_row or row.get(unique_key) in (None, ""):
        return None
    set_sql = ", ".join(f"{sql_identifier(column)} = {sql_value(value)}" for column, value in update_row.items())
    return f"UPDATE {sql_identifier(table)} SET {set_sql} WHERE {sql_identifier(unique_key)} = {sql_literal(row.get(unique_key))}"


def execute_cellx_bulk_import(table, rows, mappings, safety):
    if safety != "approved_write":
        raise ValueError("Safety Mode must be approved_write before writing to CellX.")
    if not DB_USER or not DB_PASSWORD:
        raise RuntimeError("Database is not configured.")

    schema_map = load_cellx_schema_map()
    if table not in schema_map:
        raise ValueError(f"Table {table} does not exist in CellX database.")

    columns = schema_map[table]
    writable_columns = {
        name: column for name, column in columns.items()
        if name not in {"id"} and not name.endswith("_surl")
    }
    mapped_rows, skipped_columns = mapped_rows_for_cellx(rows, mappings, writable_columns)
    unique_key = "provider_listing_id" if "provider_listing_id" in columns else None

    statements = ["START TRANSACTION"]
    prepared_rows = []
    for mapped in mapped_rows:
        insert_row = add_insert_defaults(dict(mapped), writable_columns)
        statements.append(build_insert_if_missing_sql(table, insert_row, unique_key))
        if unique_key and mapped.get(unique_key) not in (None, ""):
            update_row = add_update_defaults(dict(mapped), writable_columns)
            update_sql = build_update_sql(table, update_row, unique_key)
            if update_sql:
                statements.append(update_sql)
        prepared_rows.append(insert_row)
    statements.append("COMMIT")
    sql = ";\n".join(statements) + ";"

    result = mysql_query(sql, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "CellX database write failed.")

    return {
        "ok": True,
        "mode": "write",
        "operation": "bulk_import",
        "tableName": table,
        "sourceRows": len(rows),
        "writtenRows": len(mapped_rows),
        "uniqueKey": unique_key,
        "skippedColumns": skipped_columns,
        "previewRows": prepared_rows[:5],
    }


def validate_read_filter(where_clause):
    text = str(where_clause or "").strip()
    if not text:
        return ""
    if re.search(r";|--|/\*|\*/|\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|replace)\b", text, re.I):
        raise ValueError("Unsafe WHERE filter for CellX query.")
    if not re.fullmatch(r"[A-Za-z0-9_`'\"%.,=<>!\s()/+-]+", text):
        raise ValueError("WHERE filter contains unsupported characters.")
    return text


def validate_sort(sort_by, columns):
    text = str(sort_by or "").strip()
    if not text:
        return ""
    parts = []
    for item in text.split(","):
        tokens = item.strip().split()
        if not tokens:
            continue
        column = tokens[0].strip("`")
        if column not in columns:
            continue
        direction = tokens[1].upper() if len(tokens) > 1 else "ASC"
        if direction not in ("ASC", "DESC"):
            direction = "ASC"
        parts.append(f"{sql_identifier(column)} {direction}")
    return ", ".join(parts)


def execute_cellx_query(table, where_clause="", sort_by="", limit=100):
    if not DB_USER or not DB_PASSWORD:
        raise RuntimeError("Database is not configured.")

    schema_map = load_cellx_schema_map()
    if table not in schema_map:
        raise ValueError(f"Table {table} does not exist in CellX database.")

    columns = schema_map[table]
    column_names = list(columns.keys())
    select_sql = ", ".join(sql_identifier(column) for column in column_names)
    sql = f"SELECT {select_sql} FROM {sql_identifier(table)}"
    where_sql = validate_read_filter(where_clause)
    if where_sql:
        sql += f" WHERE {where_sql}"
    order_sql = validate_sort(sort_by, columns)
    if order_sql:
        sql += f" ORDER BY {order_sql}"
    limit_value = max(1, min(int(float(limit or 100)), 500))
    sql += f" LIMIT {limit_value}"

    result = mysql_query(sql, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "CellX database query failed.")

    rows = []
    for line in result.stdout.splitlines():
        values = line.split("\t")
        rows.append({column: (values[index] if index < len(values) and values[index] != "NULL" else "") for index, column in enumerate(column_names)})

    return {
        "ok": True,
        "mode": "query",
        "operation": "query",
        "tableName": table,
        "row_count": len(rows),
        "rows": rows,
    }


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
    if operation == "query":
        try:
            output = execute_cellx_query(table, settings.get("whereClause") or "", settings.get("sortBy") or "", settings.get("limit") or 100)
            return {
                "ok": True,
                "status": "success",
                "message": f"Read {output['row_count']} row(s) from CellX table {table}.",
                "input": {
                    "operation": operation,
                    "tableName": table,
                    "whereClause": settings.get("whereClause") or "",
                    "sortBy": settings.get("sortBy") or "",
                    "limit": settings.get("limit") or 100,
                },
                "output": output,
                "checkedAt": datetime.now(timezone.utc).isoformat(),
            }, 200
        except Exception as exc:
            return {
                "ok": False,
                "status": "error",
                "message": str(exc),
                "input": {
                    "operation": operation,
                    "tableName": table,
                    "whereClause": settings.get("whereClause") or "",
                    "sortBy": settings.get("sortBy") or "",
                    "limit": settings.get("limit") or 100,
                },
                "output": {"ok": False, "message": str(exc)},
            }, 500

    should_write = operation in ("insert", "upsert", "bulk_import") and safety == "approved_write" and str(settings.get("executeWrite") or "true").lower() != "false"
    if should_write:
        try:
            output = execute_cellx_bulk_import(table, rows, mappings, safety)
            return {
                "ok": True,
                "status": "success",
                "message": f"Wrote {output['writtenRows']} row(s) into CellX table {table}.",
                "input": {
                    "operation": operation,
                    "tableName": table,
                    "inputPayload": settings.get("inputPayload") or "{{previous_step.rows}}",
                    "sourceRows": len(rows),
                    "mappingCount": len(mappings),
                    "safetyMode": safety,
                },
                "output": output,
                "checkedAt": datetime.now(timezone.utc).isoformat(),
            }, 200
        except Exception as exc:
            return {
                "ok": False,
                "status": "error",
                "message": str(exc),
                "input": {
                    "operation": operation,
                    "tableName": table,
                    "inputPayload": settings.get("inputPayload") or "{{previous_step.rows}}",
                    "sourceRows": len(rows),
                    "mappingCount": len(mappings),
                    "safetyMode": safety,
                },
                "output": {"ok": False, "message": str(exc)},
            }, 500

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
            "note": "Preview only. Set Safety Mode to approved_write to execute real inserts/updates.",
        },
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }, 200


def first_previous_output(payload):
    previous_outputs = payload.get("previousOutputs") or []
    for item in previous_outputs:
        if isinstance(item, dict) and item.get("output") is not None:
            return item.get("output")
        if isinstance(item, (dict, list)):
            return item
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


def render_template_text(template, context):
    template = str(template or "")

    def replace(match):
        value = resolve_json_path(context, match.group(1).strip())
        if value is None and isinstance(context, dict) and "result" in context:
            value = resolve_json_path(context.get("result"), match.group(1).strip())
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2)
        return "" if value is None else str(value)

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace, template)


def all_previous_outputs(payload):
    outputs = []
    for item in payload.get("previousOutputs") or []:
        if isinstance(item, dict) and item.get("output") is not None:
            outputs.append(item.get("output"))
        elif isinstance(item, (dict, list)):
            outputs.append(item)
    return outputs


def get_case_insensitive(row, keys):
    if not isinstance(row, dict):
        return ""
    lookup = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lookup.get(str(key).lower())
        if value not in (None, ""):
            return value
    return ""


def email_context_from_outputs(outputs):
    for output in outputs:
        if not isinstance(output, dict):
            continue
        if resolve_json_path(output, "row.email_body") or resolve_json_path(output, "result.email_body") or resolve_json_path(output, "email.body") or resolve_json_path(output, "email_body"):
            return output
    return outputs[0] if outputs else {}


def client_recipients_from_outputs(outputs):
    recipients = []
    seen = set()
    for output in outputs:
        rows = find_rows(output)
        for row in rows:
            email = str(get_case_insensitive(row, ["email", "Email", "client_email", "customer_email"])).strip()
            name = str(get_case_insensitive(row, ["name", "Name", "client_name", "customer_name"])).strip()
            status = str(get_case_insensitive(row, ["status", "Status"])).strip().lower()
            if not email or "@" not in email or email.lower() in seen:
                continue
            if status in {"inactive", "disabled", "deleted", "unsubscribe", "unsubscribed", "opt_out", "opt-out", "0", "false", "no"}:
                continue
            recipients.append({"name": name or email.split("@")[0], "email": email})
            seen.add(email.lower())
    return recipients


def extract_response_text(data):
    if isinstance(data, dict) and isinstance(data.get("output_text"), str):
        return data["output_text"]
    parts = []
    for item in data.get("output", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def parse_json_from_text(text):
    text = str(text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.I | re.S)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


def limit_output_rows(value, max_rows):
    if not max_rows or max_rows < 1:
        return value
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        limited = dict(value)
        limited["rows"] = value["rows"][:max_rows]
        limited["row_count"] = min(int(value.get("row_count") or len(value["rows"])), max_rows)
        return limited
    return value


def compact_output_fields(value, fields):
    if not fields:
        return value
    rows = find_rows(value)
    if not rows:
        return value
    compact_rows = []
    for row in rows:
        if isinstance(row, dict):
            compact_rows.append({field: row.get(field) for field in fields if field in row})
        else:
            compact_rows.append(row)
    if isinstance(value, dict):
        compact = dict(value)
        compact["rows"] = compact_rows
        return compact
    return {"rows": compact_rows}


def merge_ai_rows_with_source(parsed, source_output):
    ai_rows = parsed.get("rows")
    source_rows = find_rows(source_output)
    if not isinstance(ai_rows, list) or not source_rows:
        return parsed

    by_id = {}
    for source in source_rows:
        if not isinstance(source, dict):
            continue
        key = source.get("id") or source.get("provider_listing_id") or source.get("mls_number")
        if key is not None:
            by_id[str(key)] = source

    merged_rows = []
    for index, ai_row in enumerate(ai_rows):
        if not isinstance(ai_row, dict):
            merged_rows.append(ai_row)
            continue
        key = ai_row.get("id") or ai_row.get("provider_listing_id") or ai_row.get("mls_number")
        source = by_id.get(str(key)) if key is not None else None
        if source is None and index < len(source_rows) and isinstance(source_rows[index], dict):
            source = source_rows[index]
        merged_rows.append({**source, **ai_row} if source else ai_row)

    parsed["rows"] = merged_rows
    return parsed


def openai_model_preview(payload):
    settings = payload.get("settings") or {}
    previous_output = first_previous_output(payload)
    full_previous_output = previous_output
    max_input_rows_raw = settings.get("maxInputRows")
    if not max_input_rows_raw and "Property Analyst" in str(payload.get("nodeName") or ""):
        max_input_rows_raw = 3
    try:
        max_input_rows = max(1, min(int(max_input_rows_raw), 25)) if max_input_rows_raw else None
    except Exception:
        max_input_rows = None
    previous_output = limit_output_rows(previous_output, max_input_rows)
    full_previous_output = limit_output_rows(full_previous_output, max_input_rows)
    compact_fields = settings.get("compactInputFields") or []
    if not compact_fields and "Property Analyst" in str(payload.get("nodeName") or ""):
        compact_fields = [
            "id", "formatted_address", "city", "state", "zip_code",
            "property_type", "bedrooms", "bathrooms", "square_footage",
            "lot_size", "year_built", "hoa_fee", "price", "original_price",
            "price_cut_amount", "price_cut_percent", "days_on_market",
            "listed_date", "mls_name", "photo_1", "landing_page_url",
        ]
    if isinstance(compact_fields, str):
        compact_fields = [field.strip() for field in compact_fields.split(",") if field.strip()]
    previous_output = compact_output_fields(previous_output, compact_fields)
    mode = settings.get("authMode") or "platform_api_key"
    model = settings.get("model") or "gpt-5"
    secret_name = settings.get("platformSecretName") or "OPENAI_API_KEY"
    api_key = settings.get("apiKey") if mode == "bring_your_own_api_key" else os.getenv(secret_name) or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "ok": False,
            "status": "error",
            "message": f"Missing OpenAI API key. Configure backend secret {secret_name}.",
            "input": {"authMode": mode, "model": model, "platformSecretName": secret_name},
            "output": {"ok": False, "message": "Missing OpenAI API key."},
        }, 400

    prompt_template = settings.get("promptTemplate") or (
        "Analyze these real estate listings for a potential buyer.\n"
        "Use address, price, property facts, market signals, and price-cut data.\n"
        "Return JSON with rows and email.\n\nPrevious workflow output:\n{{previous_step}}"
    )
    prompt = render_template_text(prompt_template, previous_output)
    return_format = settings.get("returnFormat") or "{}"
    instructions = (
        "You are a real estate analyst assistant. Be practical, concise, and transparent. "
        "Do not make legal, mortgage, or guaranteed investment claims. "
        "Return only valid JSON matching the requested structure."
    )
    base_url = (settings.get("baseUrl") or "https://api.openai.com/v1").rstrip("/")
    model_candidates = []
    for candidate in (model, "gpt-5", "gpt-4o-mini"):
        if candidate and candidate not in model_candidates:
            model_candidates.append(candidate)

    data = None
    used_model = model
    last_http_error = None
    for candidate in model_candidates:
        request_body = {
            "model": candidate,
            "instructions": instructions,
            "input": f"{prompt}\n\nExpected JSON shape:\n{return_format}",
            "text": {"format": {"type": "json_object"}},
        }
        request = Request(
            f"{base_url}/responses",
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        if settings.get("projectId"):
            request.add_header("OpenAI-Project", settings.get("projectId"))

        try:
            with urlopen(request, timeout=60) as handle:
                data = json.loads(handle.read().decode("utf-8"))
                used_model = candidate
                break
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_http_error = (exc.code, detail, candidate)
            if exc.code == 404 and candidate != model_candidates[-1]:
                continue
            return {
                "ok": False,
                "status": "error",
                "message": f"OpenAI API error: HTTP {exc.code}",
                "input": {"authMode": mode, "model": candidate, "platformSecretName": secret_name},
                "output": {"ok": False, "message": detail[:1000]},
            }, 502
        except URLError as exc:
            return {
                "ok": False,
                "status": "error",
                "message": f"OpenAI API connection failed: {exc.reason}",
                "input": {"authMode": mode, "model": candidate, "platformSecretName": secret_name},
                "output": {"ok": False, "message": str(exc.reason)},
            }, 502

    if data is None:
        code, detail, candidate = last_http_error or ("unknown", "No response from OpenAI.", model)
        return {
            "ok": False,
            "status": "error",
            "message": f"OpenAI API error: HTTP {code}",
            "input": {"authMode": mode, "model": candidate, "platformSecretName": secret_name},
            "output": {"ok": False, "message": str(detail)[:1000]},
        }, 502

    text = extract_response_text(data)
    parsed = parse_json_from_text(text)
    if not isinstance(parsed, dict):
        return {
            "ok": False,
            "status": "error",
            "message": "OpenAI returned text that could not be parsed as JSON.",
            "input": {"authMode": mode, "model": model, "platformSecretName": secret_name},
            "output": {"ok": False, "raw": text[:2000]},
        }, 502

    if "rows" not in parsed:
        source_rows = find_rows(full_previous_output)
        if source_rows:
            parsed["rows"] = source_rows
    else:
        parsed = merge_ai_rows_with_source(parsed, full_previous_output)
    parsed["ok"] = True
    parsed["mode"] = "openai_property_analysis"

    return {
        "ok": True,
        "status": "success",
        "message": f"OpenAI analyzed {len(find_rows(parsed))} property row(s).",
        "input": {
            "authMode": mode,
            "model": used_model,
            "requestedModel": model,
            "platformSecretName": secret_name,
            "previousRows": len(find_rows(previous_output)),
        },
        "output": parsed,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }, 200


def email_preview(payload):
    settings = payload.get("settings") or {}
    previous_outputs = all_previous_outputs(payload)
    previous_output = email_context_from_outputs(previous_outputs)
    clients = client_recipients_from_outputs(previous_outputs)
    recipient = settings.get("to") or ",".join(client["email"] for client in clients) or resolve_json_path(previous_output, "email.to") or ""
    subject_template = settings.get("subjectTemplate") or "{{email.subject}}"
    body_template = settings.get("bodyTemplate") or "{{email.body}}"
    subject = render_template_text(subject_template, previous_output)
    body = render_template_text(body_template, previous_output)
    if not subject:
        subject = (
            resolve_json_path(previous_output, "row.email_subject")
            or resolve_json_path(previous_output, "result.email_subject")
            or resolve_json_path(previous_output, "email_subject")
            or resolve_json_path(previous_output, "rows.0.email_subject")
            or resolve_json_path(previous_output, "email.subject")
            or "AI property recommendations"
        )
    if not body:
        body = (
            resolve_json_path(previous_output, "row.email_body")
            or resolve_json_path(previous_output, "result.email_body")
            or resolve_json_path(previous_output, "email_body")
            or resolve_json_path(previous_output, "rows.0.email_body")
            or resolve_json_path(previous_output, "email.body")
            or render_template_text("{{summary}}", previous_output)
        )
    mode = settings.get("deliveryMode") or "preview"
    provider = payload.get("nodeName") or "Email"
    username = settings.get("username") or os.getenv("GMAIL_USERNAME") or os.getenv("SMTP_USERNAME") or ""
    from_email = settings.get("fromEmail") or username
    secret_name = settings.get("passwordSecretName") or "GMAIL_APP_PASSWORD"
    password = os.getenv(secret_name) or os.getenv("GMAIL_APP_PASSWORD") or os.getenv("SMTP_PASSWORD") or ""
    smtp_host = settings.get("smtpHost") or os.getenv("SMTP_HOST") or "smtp.gmail.com"
    smtp_port = int(settings.get("smtpPort") or os.getenv("SMTP_PORT") or "587")
    smtp_security = settings.get("smtpSecurity") or os.getenv("SMTP_SECURITY") or "starttls"
    personalized_clients = clients if clients and not settings.get("to") else []

    def render_for_client(client):
        context = dict(previous_output) if isinstance(previous_output, dict) else {"previous_step": previous_output}
        context["client"] = client
        client_subject = render_template_text(subject_template, context) or subject
        client_body = render_template_text(body_template, context) or body
        return client_subject, client_body

    if mode == "connected_provider":
        missing = []
        if not recipient:
            missing.append("to")
        if not subject:
            missing.append("subject")
        if not body:
            missing.append("body")
        if not username:
            missing.append("username")
        if not password:
            missing.append(secret_name)
        if missing:
            return {
                "ok": False,
                "status": "error",
                "message": f"Missing email send settings: {', '.join(missing)}",
                "input": {
                    "deliveryMode": mode,
                    "to": recipient,
                    "subjectTemplate": settings.get("subjectTemplate") or "{{email.subject}}",
                    "bodyTemplate": settings.get("bodyTemplate") or "{{email.body}}",
                    "smtpHost": smtp_host,
                    "smtpPort": smtp_port,
                    "smtpSecurity": smtp_security,
                    "username": username,
                    "passwordSecretName": secret_name,
                },
            }, 400

        sent = []
        try:
            if smtp_security == "ssl":
                with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=25) as smtp:
                    smtp.login(username, password)
                    targets = personalized_clients or [{"name": "", "email": recipient}]
                    for client in targets:
                        client_subject, client_body = render_for_client(client)
                        message = EmailMessage()
                        message["From"] = from_email
                        message["To"] = client["email"]
                        message["Subject"] = client_subject
                        message.set_content(client_body)
                        smtp.send_message(message)
                        sent.append({"name": client.get("name") or "", "email": client["email"]})
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=25) as smtp:
                    if smtp_security == "starttls":
                        smtp.starttls()
                    smtp.login(username, password)
                    targets = personalized_clients or [{"name": "", "email": recipient}]
                    for client in targets:
                        client_subject, client_body = render_for_client(client)
                        message = EmailMessage()
                        message["From"] = from_email
                        message["To"] = client["email"]
                        message["Subject"] = client_subject
                        message.set_content(client_body)
                        smtp.send_message(message)
                        sent.append({"name": client.get("name") or "", "email": client["email"]})
        except Exception as exc:
            return {
                "ok": False,
                "status": "error",
                "message": f"Email send failed: {exc}",
                "input": {
                    "deliveryMode": mode,
                    "to": recipient,
                    "smtpHost": smtp_host,
                    "smtpPort": smtp_port,
                    "smtpSecurity": smtp_security,
                    "username": username,
                    "passwordSecretName": secret_name,
                },
            }, 502

        return {
            "ok": True,
            "status": "success",
            "message": f"Email sent to {len(sent)} client(s).",
            "input": {
                "deliveryMode": mode,
                "to": recipient,
                "clientCount": len(personalized_clients),
                "smtpHost": smtp_host,
                "smtpPort": smtp_port,
                "smtpSecurity": smtp_security,
                "username": username,
                "passwordSecretName": secret_name,
            },
            "output": {
                "ok": True,
                "mode": "email_sent",
                "provider": provider,
                "to": recipient,
                "sent": sent,
                "subject": subject,
                "body": body,
                "sentAt": datetime.now(timezone.utc).isoformat(),
            },
            "checkedAt": datetime.now(timezone.utc).isoformat(),
        }, 200

    return {
        "ok": True,
        "status": "success",
        "message": "Email preview generated. Change Delivery Mode to connected provider to send automatically.",
        "input": {
            "deliveryMode": mode,
            "to": recipient,
            "clientCount": len(clients),
            "subjectTemplate": settings.get("subjectTemplate") or "{{email.subject}}",
            "bodyTemplate": settings.get("bodyTemplate") or "{{email.body}}",
        },
        "output": {
            "ok": True,
            "mode": "email_preview" if mode == "preview" else "email_ready",
            "provider": provider,
            "to": recipient,
            "subject": subject,
            "body": render_for_client(clients[0])[1] if clients else body,
            "clientPreviews": [
                {"name": client["name"], "email": client["email"], "subject": render_for_client(client)[0]}
                for client in clients[:10]
            ],
            "attachmentHint": "Use Export Results to download the listing rows as Excel, or connect a real mail provider to attach files automatically.",
        },
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
    env = {
        "PATH": os.getenv("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
        "PYTHONIOENCODING": "utf-8",
    }
    for key in ("RENTCAST_API_KEY", "ATTOM_API_KEY", "ESTATED_API_KEY", "BRIDGE_API_KEY"):
        if os.getenv(key):
            env[key] = os.getenv(key)
    return env


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
    if node_type == "cellx-db" and (settings.get("operation") or "query") != "delete":
        required = [field for field in required if field != "softDelete"]
    if node_name == "JSON Transform" or "json-transform" in str(payload.get("action") or ""):
        required = [field for field in required if field not in ("endpoint", "timeout")]
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

    if node_type == "communication" and ("mail" in str(payload.get("action") or "") or "gmail/send" in str(payload.get("action") or "")):
        return email_preview(payload)

    if node_type == "ai" and ("openai" in node_name.lower() or "openai" in str(payload.get("action") or "").lower()):
        return openai_model_preview(payload)

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
        elif path == "/marketplace/templates":
            status, data = response(marketplace_templates())
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
        elif path == "/marketplace/templates":
            body, status = create_marketplace_template(payload)
            status, data = response(body, status)
        elif path == "/marketplace/purchase":
            body, status = purchase_marketplace_template(payload)
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
