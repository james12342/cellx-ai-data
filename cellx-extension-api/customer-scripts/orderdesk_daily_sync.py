#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from orderdesk_orders_to_db import clean, normalize_order, order_list, request_json
from urllib.parse import urlencode


ORDERDESK_API_BASE = "https://app.orderdesk.me/api"
TABLE_NAME = "cx_orderdesk_order"
SYNC_COLUMNS = [
    "provider",
    "provider_listing_id",
    "orderdesk_order_id",
    "order_id",
    "source_name",
    "status",
    "order_date",
    "updated_date",
    "customer_name",
    "customer_email",
    "customer_phone",
    "ship_name",
    "ship_company",
    "ship_address1",
    "ship_address2",
    "ship_city",
    "ship_state",
    "ship_postal_code",
    "ship_country",
    "currency",
    "order_total",
    "shipping_total",
    "tax_total",
    "discount_total",
    "item_count",
    "quantity_total",
    "items_json",
    "raw_json",
    "last_synced_at",
    "owner",
    "dept_id",
    "create_by",
    "create_time",
    "update_by",
    "update_time",
    "del_flag",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Sync recent OrderDesk orders into CellX MySQL.")
    parser.add_argument("--max-records", type=int, default=int(os.getenv("ORDERDESK_SYNC_MAX_RECORDS", "5000")))
    parser.add_argument("--page-size", type=int, default=int(os.getenv("ORDERDESK_SYNC_PAGE_SIZE", "500")))
    parser.add_argument("--order-by", default=os.getenv("ORDERDESK_SYNC_ORDER_BY", "date_added"))
    parser.add_argument("--order", default=os.getenv("ORDERDESK_SYNC_ORDER", "desc"))
    parser.add_argument("--folder-id", default=os.getenv("ORDERDESK_SYNC_FOLDER_ID", ""))
    parser.add_argument("--request-timeout", type=int, default=int(os.getenv("ORDERDESK_SYNC_REQUEST_TIMEOUT", "20")))
    return parser.parse_args()


def sql_identifier(name):
    if not str(name).replace("_", "").isalnum():
        raise ValueError(f"Unsafe SQL identifier: {name}")
    return f"`{name}`"


def mysql_datetime(value):
    text = clean(value)
    if not text:
        return None
    text = text.replace("T", " ").replace("Z", "")
    return text[:19] if len(text) >= 19 else text


def sql_literal(value):
    if value is None or value == "":
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    text = str(value)
    return "'" + text.replace("\\", "\\\\").replace("'", "''") + "'"


def mysql_query(sql, timeout=180):
    db_user = os.getenv("DB_USER", "")
    db_password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "cellx_base")
    if not db_user or not db_password:
        raise RuntimeError("DB_USER and DB_PASSWORD must be configured.")

    env = os.environ.copy()
    env["MYSQL_PWD"] = db_password
    cmd = [
        "mysql",
        "-h",
        os.getenv("DB_HOST", "127.0.0.1"),
        "-P",
        os.getenv("DB_PORT", "3306"),
        "-u",
        db_user,
        "-D",
        db_name,
        "-N",
        "-B",
    ]
    result = subprocess.run(cmd, input=sql, env=env, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "MySQL write failed.")
    return result


def prepare_row(row):
    prepared = {column: row.get(column) for column in SYNC_COLUMNS if column in row}
    prepared["last_synced_at"] = mysql_datetime(prepared.get("last_synced_at")) or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    prepared["order_date"] = mysql_datetime(prepared.get("order_date"))
    prepared["updated_date"] = mysql_datetime(prepared.get("updated_date"))
    prepared.setdefault("owner", "workflow")
    prepared.setdefault("dept_id", 0)
    prepared.setdefault("create_by", "workflow")
    prepared.setdefault("update_by", "workflow")
    prepared.setdefault("del_flag", "0")
    return prepared


def upsert_orders(rows):
    if not rows:
        return 0

    statements = []
    writable_columns = [column for column in SYNC_COLUMNS if column != "create_time" and column != "update_time"]
    insert_columns = writable_columns + ["create_time", "update_time"]
    update_columns = [column for column in writable_columns if column not in ("provider_listing_id", "create_by", "owner", "dept_id", "del_flag")]
    batch_size = 25

    for batch_start in range(0, len(rows), batch_size):
        statements.append("START TRANSACTION")
        for row in rows[batch_start:batch_start + batch_size]:
            prepared = prepare_row(row)
            values = []
            for column in insert_columns:
                if column in ("create_time", "update_time"):
                    values.append("NOW()")
                else:
                    values.append(sql_literal(prepared.get(column)))
            updates = [f"{sql_identifier(column)} = VALUES({sql_identifier(column)})" for column in update_columns]
            updates.append("`update_time` = NOW()")
            statements.append(
                f"INSERT INTO {sql_identifier(TABLE_NAME)} "
                f"({', '.join(sql_identifier(column) for column in insert_columns)}) "
                f"VALUES ({', '.join(values)}) "
                f"ON DUPLICATE KEY UPDATE {', '.join(updates)}"
            )
        statements.append("COMMIT")

    mysql_query(";\n".join(statements) + ";")
    return len(rows)


def fetch_orders(args):
    store_id = clean(os.getenv("ORDERDESK_STORE_ID"))
    api_key = clean(os.getenv("ORDERDESK_API_KEY"))
    if not store_id or not api_key:
        raise RuntimeError("ORDERDESK_STORE_ID and ORDERDESK_API_KEY must be configured.")

    page_size = max(1, min(500, args.page_size))
    max_records = max(1, min(5000, args.max_records))
    params = {
        "limit": page_size,
        "offset": 0,
        "order_by": args.order_by or "date_added",
        "order": args.order or "desc",
    }
    if args.folder_id:
        params["folder_id"] = args.folder_id

    base_url = clean(os.getenv("ORDERDESK_API_BASE") or ORDERDESK_API_BASE).rstrip("/")
    orders = []
    source_url = ""
    while len(orders) < max_records:
        page_params = dict(params)
        page_params["offset"] = len(orders)
        url = f"{base_url}/orders?{urlencode(page_params)}"
        if not source_url:
            source_url = url
        response = request_json(url, store_id, api_key, args.request_timeout)
        page_orders = order_list(response)
        if not page_orders:
            break
        orders.extend(page_orders[: max_records - len(orders)])
        if len(page_orders) < page_size:
            break

    return source_url, [normalize_order(order) for order in orders]


def main():
    args = parse_args()
    source_url, rows = fetch_orders(args)
    written = upsert_orders(rows)
    print(json.dumps({
        "ok": True,
        "provider": "OrderDesk",
        "table": TABLE_NAME,
        "source_url": source_url,
        "fetched_rows": len(rows),
        "written_rows": written,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
