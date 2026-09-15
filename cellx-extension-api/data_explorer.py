"""Admin-only physical MySQL explorer; registry associations remain draft metadata.

GET /data-explorer/{status,catalog,table,rows}. table/rows require table=NAME.
Rows accept page (1), page_size (50, max 100), search, sort, direction,
and filters (JSON object of column/scalar equality predicates, max 10).
No tenant authorization is inferred from registry bindings or request claims.
PyMySQL uses the same local endpoint and DB_* credentials as server.mysql_query.
"""

from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import json
import math
from pathlib import Path
import re
import sqlite3
from time import monotonic


class ExplorerError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
SENSITIVE = (
    "api_key", "apikey", "token", "secret", "password", "passwd", "credential",
    "private", "authorization", "cookie", "session", "salt", "email", "phone",
    "mobile", "address", "birth", "dob", "ssn", "social", "passport", "license",
    "card", "bank", "account", "routing", "iban", "ip_address", "ipaddress",
    "name", "contact", "health", "medical", "salary", "payload", "config",
    "setting", "message", "body", "content", "note", "url", "uri", "hash",
    "postal", "zip", "city", "street", "latitude", "longitude", "fax",
    "pwd", "access_key", "accesskey", "connection_string", "connectionstring", "pin",
)
SAFE_TYPES = {
    "tinyint", "smallint", "mediumint", "int", "bigint", "decimal", "float",
    "double", "date", "datetime", "timestamp", "time", "year", "char", "varchar",
}
SAFE_TEXT_COLUMNS = {
    "status", "state", "category", "type", "sku", "product_code", "product_sku",
    "carrier", "currency", "currency_code", "unit", "unit_code", "country_code",
    "order_status", "shipping_status", "payment_status",
}
SENSITIVE_TABLES = ("secret", "credential", "session", "token", "password", "config",
                    "audit", "log", "user", "account", "auth", "setting")


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ExplorerError(400, "invalid_identifier")
    return "`" + value + "`"


@contextmanager
def mysql_connection(database, user, password):
    if not database or not user or not password:
        raise ExplorerError(503, "database_not_configured")
    try:
        import pymysql
    except ImportError:
        raise ExplorerError(503, "database_driver_unavailable") from None
    db = pymysql.connect(host="127.0.0.1", port=3306, database=database,
                         user=user, password=password, charset="utf8mb4",
                         connect_timeout=5, read_timeout=10, write_timeout=5,
                         autocommit=False, local_infile=False,
                         cursorclass=pymysql.cursors.DictCursor)
    try:
        with db.cursor() as cursor:
            cursor.execute("START TRANSACTION READ ONLY")
        yield db
    finally:
        try:
            db.rollback()
        finally:
            db.close()


def select(db, sql, params=(), limit=10001):
    if not sql.lstrip().startswith("SELECT "):
        raise ExplorerError(500, "read_only_violation")
    with db.cursor() as cursor:
        cursor.execute(sql.replace("SELECT ", "SELECT /*+ MAX_EXECUTION_TIME(5000) */ ", 1), params)
        rows = cursor.fetchmany(limit)
    if len(rows) >= limit:
        raise ExplorerError(503, "catalog_limit_exceeded")
    return rows


def registry_bindings(path):
    if not path or not Path(path).is_file():
        return [], False
    try:
        db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
        db.row_factory = sqlite3.Row
        deadline = monotonic() + 0.25
        remaining_steps = 200
        def budget():
            nonlocal remaining_steps
            remaining_steps -= 1
            return int(remaining_steps <= 0 or monotonic() >= deadline)
        db.set_progress_handler(budget, 1000)
        try:
            if db.execute("PRAGMA application_id").fetchone()[0] != 1128354642:
                return [], False
            rows = db.execute("""SELECT t.physical_name, t.tenant_id AS company_id,
                company.name AS company_name, a.id, a.name, a.state, u.state AS use_state
                FROM table_registry t JOIN tenants company ON company.id=t.tenant_id
                LEFT JOIN table_use u
                ON t.id=u.table_id AND t.tenant_id=u.tenant_id
                LEFT JOIN agents a ON a.id=u.agent_id AND a.tenant_id=u.tenant_id
                ORDER BY t.physical_name,a.id LIMIT 10001""").fetchall()
        finally:
            db.close()
        if len(rows) > 10000:
            return [], False
        grouped = {}
        for row in rows:
            item = grouped.setdefault(row["physical_name"], {"name": row["physical_name"], "state": "planned",
                "company_id": row["company_id"], "company_name": row["company_name"], "agents": []})
            if row["id"]:
                item["agents"].append({key: row[key] for key in ("id", "name", "state", "use_state", "company_id")})
        return list(grouped.values()), True
    except sqlite3.Error:
        return [], False


def catalog(db, registry_path):
    columns = select(db, """SELECT c.TABLE_NAME AS table_name, c.COLUMN_NAME AS name,
        c.DATA_TYPE AS type, c.IS_NULLABLE AS nullable, c.COLUMN_KEY AS column_key,
        c.CHARACTER_MAXIMUM_LENGTH AS max_length
        FROM information_schema.COLUMNS c JOIN information_schema.TABLES t
        ON c.TABLE_SCHEMA=t.TABLE_SCHEMA AND c.TABLE_NAME=t.TABLE_NAME
        WHERE c.TABLE_SCHEMA=DATABASE() AND t.TABLE_TYPE='BASE TABLE'
        ORDER BY c.TABLE_NAME,c.ORDINAL_POSITION LIMIT 10001""")
    tables = {}
    for col in columns:
        name = col["table_name"]
        if not IDENTIFIER.fullmatch(name) or not IDENTIFIER.fullmatch(col["name"]):
            continue
        table = tables.setdefault(name, {"name": name, "physical_exists": True,
                                        "association": "unlinked", "company_id": None, "company_name": None,
                                        "agents": [], "columns": [], "relations": []})
        masked = (any(word in col["name"].lower() for word in SENSITIVE)
                  or any(word in name.lower() for word in SENSITIVE_TABLES)
                  or col["type"] not in SAFE_TYPES
                  or (col["type"] in {"char", "varchar"}
                      and (col["name"].lower() not in SAFE_TEXT_COLUMNS or (col["max_length"] or 0) > 512)))
        table["columns"].append({"name": col["name"], "type": col["type"],
                                 "nullable": col["nullable"] == "YES",
                                 "primary_key": col["column_key"] == "PRI", "masked": masked})
    relations = select(db, """SELECT TABLE_NAME AS table_name, COLUMN_NAME AS col,
        REFERENCED_TABLE_NAME AS target, REFERENCED_COLUMN_NAME AS target_col
        FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE()
        AND REFERENCED_TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY TABLE_NAME,ORDINAL_POSITION LIMIT 10001""")
    for rel in relations:
        if rel["table_name"] in tables and rel["target"] in tables:
            tables[rel["table_name"]]["relations"].append({"column": rel["col"],
                "referenced_table": rel["target"], "referenced_column": rel["target_col"]})
    planned, available = registry_bindings(registry_path)
    companies, agents = {}, {}
    for table in tables.values():
        table["all_columns_masked"] = all(c["masked"] for c in table["columns"])
    for item in planned:
        companies[item["company_id"]] = {"id": item["company_id"], "name": item["company_name"]}
        for agent in item["agents"]:
            agents[agent["id"]] = {k: agent[k] for k in ("id", "name", "state", "company_id")}
        item["physical_exists"] = item["name"] in tables
        if item["physical_exists"]:
            tables[item["name"]].update(association="registry_planned", agents=item["agents"],
                                       company_id=item["company_id"], company_name=item["company_name"])
    return {"ok": True, "read_only": True, "tables": list(tables.values()),
            "planned_tables": planned, "registry_available": available,
            "companies": list(companies.values()), "agents": list(agents.values()),
            "limitations": ["Admin access only; tenant authorization is unsupported.",
                "Company and agent grouping comes from registry drafts, not runtime saved workflows.",
                "A matching physical name does not verify registry deployment, ownership or schema equivalence.",
                "Company and agent lists include only registry table bindings.",
                "Sensitive and system tables are masked. Text is masked except approved operational columns; free text, JSON, binary and long strings are always masked.",
                "Masked columns cannot be searched, filtered or sorted. Column policy is conservative, not a content classification guarantee.",
                "Tables without an unmasked primary key have no guaranteed paging order."]}


def integer(query, key, default, maximum):
    raw = query.get(key, str(default))
    if not re.fullmatch(r"[0-9]{1,6}", raw) or not 1 <= int(raw) <= maximum:
        raise ExplorerError(400, "invalid_" + key)
    return int(raw)


def value_json(value):
    if type(value) is int and abs(value) > 9007199254740991:
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (Decimal, timedelta)):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, bytes):
        return "[REDACTED]"
    return value


def records(db, table, query):
    columns = {c["name"]: c for c in table["columns"]}
    if len(columns) > 256:
        raise ExplorerError(400, "table_too_wide")
    def usable(name):
        identifier(name)
        if name not in columns:
            raise ExplorerError(400, "unknown_column")
        if columns[name]["masked"]:
            raise ExplorerError(403, "sensitive_column")
        return identifier(name)
    page = integer(query, "page", 1, 1000)
    size = integer(query, "page_size", 50, 100)
    offset = (page - 1) * size
    if offset > 10000:
        raise ExplorerError(400, "page_limit_exceeded")
    direction = query.get("direction", "asc")
    if direction not in {"asc", "desc"}:
        raise ExplorerError(400, "invalid_direction")
    sort = query.get("sort") or next((c["name"] for c in columns.values() if c["primary_key"] and not c["masked"]), None)
    order = [usable(sort) + " " + direction] if sort else []
    order.extend(usable(c["name"]) + " ASC" for c in columns.values()
                 if c["primary_key"] and not c["masked"] and c["name"] != sort)
    try:
        filters = json.loads(query.get("filters", "{}"))
    except (ValueError, TypeError):
        raise ExplorerError(400, "invalid_filters") from None
    if not isinstance(filters, dict) or len(filters) > 10:
        raise ExplorerError(400, "invalid_filters")
    where, params = [], []
    for key, value in filters.items():
        column = usable(key)
        if value is not None and (type(value) not in (str, int, float, bool) or len(str(value)) > 256
                                  or isinstance(value, float) and not math.isfinite(value)):
            raise ExplorerError(400, "invalid_filter_value")
        placeholder = "%s"
        if columns[key]["type"] == "bigint" and isinstance(value, str):
            if not re.fullmatch(r"-?[0-9]{1,20}", value):
                raise ExplorerError(400, "invalid_filter_value")
            # MySQL string/numeric comparison can otherwise coerce BIGINT to double.
            placeholder = "CAST(%s AS DECIMAL(65,0))"
        where.append(column + (" IS NULL" if value is None else " = " + placeholder))
        if value is not None:
            params.append(value)
    search = query.get("search", "")
    if len(search) > 128:
        raise ExplorerError(400, "search_too_long")
    if search:
        searchable = [c for c in columns.values() if not c["masked"] and c["type"] in {"char", "varchar"}]
        if not searchable:
            raise ExplorerError(400, "no_searchable_columns")
        where.append("(" + " OR ".join("LOCATE(%s, " + usable(c["name"]) + ") > 0" for c in searchable) + ")")
        params.extend([search] * len(searchable))
    # Sensitive values never leave MySQL; even filtering/ordering by them is denied.
    projection = ["NULL AS " + identifier(c["name"]) if c["masked"] else identifier(c["name"]) for c in columns.values()]
    sql = "SELECT " + ", ".join(projection) + " FROM " + identifier(table["name"])
    if where:
        sql += " WHERE " + " AND ".join(where)
    if order:
        sql += " ORDER BY " + ", ".join(order)
    sql += " LIMIT %s OFFSET %s"
    params.extend([size + 1, offset])
    rows = select(db, sql, tuple(params), limit=size + 2)
    output = [{name: "[REDACTED]" if col["masked"] else value_json(row.get(name))
               for name, col in columns.items()} for row in rows[:size]]
    return {"ok": True, "read_only": True, "table": table["name"], "columns": table["columns"],
            "rows": output, "page": page, "page_size": size, "has_more": len(rows) > size,
            "sort": sort, "direction": direction}


def handle_request(method, path, headers, query, *, authorize, connect, registry_path=None, allowed_origin=None):
    try:
        # Only pass headers into the trusted server helper: body/query tokens and identity claims cannot authorize.
        try:
            allowed, _, status = authorize(headers=headers)
        except (TypeError, ValueError):
            allowed, status = False, 401
        if not allowed:
            raise ExplorerError(401 if status != 503 else 403, "admin_required")
        if headers.get("Origin") and headers.get("Origin") != allowed_origin:
            raise ExplorerError(403, "origin_not_allowed")
        if method != "GET":
            raise ExplorerError(405, "read_only")
        operation = path.removeprefix("/data-explorer/")
        if operation not in {"status", "catalog", "table", "rows"}:
            raise ExplorerError(404, "not_found")
        permitted = {"table"} if operation == "table" else ({"table", "page", "page_size", "sort", "direction", "search", "filters"} if operation == "rows" else set())
        if set(query) - permitted or any(not isinstance(v, list) or len(v) != 1 or not isinstance(v[0], str) or len(v[0]) > 4096 for v in query.values()):
            raise ExplorerError(400, "invalid_query")
        query = {k: v[0] for k, v in query.items()}
        with connect() as db:
            inventory = catalog(db, registry_path)
            if operation == "status":
                return {"ok": True, "read_only": True, "admin_only": True,
                        "tenant_access_supported": False, "database_available": True,
                        "registry_available": inventory["registry_available"]}, 200
            if operation == "catalog":
                return inventory, 200
            name = query.get("table", "")
            identifier(name)
            table = next((t for t in inventory["tables"] if t["name"] == name), None)
            if table is None:
                raise ExplorerError(404, "table_not_found")
            return ({"ok": True, "table": table} if operation == "table" else records(db, table, query)), 200
    except ExplorerError as exc:
        return {"ok": False, "code": exc.code}, exc.status
    except Exception:
        # Driver errors can contain SQL, credentials, paths and row values.
        return {"ok": False, "code": "database_unavailable"}, 503
