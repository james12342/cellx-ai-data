#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ORDERDESK_API_BASE = "https://app.orderdesk.me/api"


def read_payload():
    raw = sys.stdin.read().strip() or "{}"
    try:
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def number(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except Exception:
        return None


def pick(data, *paths):
    for path in paths:
        current = data
        found = True
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                found = False
                break
        if found and current not in (None, ""):
            return current
    return ""


def as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def request_json(url, store_id, api_key, timeout):
    headers = {
        "ORDERDESK-STORE-ID": store_id,
        "ORDERDESK-API-KEY": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": f"CellAIData-OrderDesk-DB-Sync/1.0 ({store_id}; https://cellaidata.com)",
    }
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset, errors="replace"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Order Desk API returned HTTP {exc.code}: {body}")
    except URLError as exc:
        raise RuntimeError(f"Order Desk API request failed: {exc.reason}")


def order_list(api_response):
    for key in ("orders", "order", "data", "results"):
        value = api_response.get(key) if isinstance(api_response, dict) else None
        if isinstance(value, list):
            return value
        if isinstance(value, dict) and isinstance(value.get("orders"), list):
            return value["orders"]
    return []


def iso_date(value):
    text = clean(value)
    if not text:
        return ""
    return text.replace("T", " ")[:19]


def customer_name(order):
    first = clean(pick(order, "shipping.first_name", "customer.first_name", "first_name"))
    last = clean(pick(order, "shipping.last_name", "customer.last_name", "last_name"))
    joined = " ".join(part for part in (first, last) if part)
    return joined or clean(pick(order, "shipping.name", "customer.name", "name"))


def address(order):
    return {
        "name": customer_name(order),
        "company": clean(pick(order, "shipping.company", "company")),
        "address1": clean(pick(order, "shipping.address1", "shipping.address_1", "address1")),
        "address2": clean(pick(order, "shipping.address2", "shipping.address_2", "address2")),
        "city": clean(pick(order, "shipping.city", "city")),
        "state": clean(pick(order, "shipping.state", "state")),
        "postal_code": clean(pick(order, "shipping.postal_code", "shipping.zip", "zip")),
        "country": clean(pick(order, "shipping.country", "country") or "US"),
        "phone": clean(pick(order, "shipping.phone", "customer.phone", "phone")),
        "email": clean(pick(order, "email", "customer.email", "shipping.email")),
    }


def items_summary(order):
    items = as_list(pick(order, "order_items", "items", "line_items"))
    normalized = []
    quantity_total = 0
    for item in items:
        quantity = number(pick(item, "quantity", "qty")) or 1
        quantity_total += quantity
        normalized.append({
            "sku": clean(pick(item, "sku", "code", "variation_id")),
            "name": clean(pick(item, "name", "product_name", "title")),
            "quantity": quantity,
            "price": number(pick(item, "price", "unit_price", "total")),
        })
    return normalized, int(quantity_total) if quantity_total else len(items)


def normalize_order(order):
    orderdesk_id = clean(pick(order, "id", "order_id", "orderdesk_id"))
    public_order_id = clean(pick(order, "source_id", "order_number", "order_id", "id"))
    shipping = address(order)
    items, quantity_total = items_summary(order)
    source_name = clean(pick(order, "source_name", "source", "store_name"))
    status = clean(pick(order, "folder_id", "folder_name", "status", "order_status"))
    order_total = number(pick(order, "total", "order_total", "grand_total"))
    shipping_total = number(pick(order, "shipping_total", "shipping", "shipping_amount"))
    tax_total = number(pick(order, "tax_total", "tax", "tax_amount"))
    discount_total = number(pick(order, "discount_total", "discount", "discount_amount"))

    return {
        "provider": "OrderDesk",
        "provider_listing_id": f"orderdesk:{orderdesk_id or public_order_id}",
        "orderdesk_order_id": orderdesk_id,
        "order_id": public_order_id,
        "source_name": source_name,
        "status": status,
        "order_date": iso_date(pick(order, "date_added", "order_date", "date")),
        "updated_date": iso_date(pick(order, "date_updated", "updated_date", "modified")),
        "customer_name": shipping["name"],
        "customer_email": shipping["email"],
        "customer_phone": shipping["phone"],
        "ship_name": shipping["name"],
        "ship_company": shipping["company"],
        "ship_address1": shipping["address1"],
        "ship_address2": shipping["address2"],
        "ship_city": shipping["city"],
        "ship_state": shipping["state"],
        "ship_postal_code": shipping["postal_code"],
        "ship_country": shipping["country"],
        "currency": clean(pick(order, "currency", "currency_code") or "USD"),
        "order_total": order_total,
        "shipping_total": shipping_total,
        "tax_total": tax_total,
        "discount_total": discount_total,
        "item_count": len(items),
        "quantity_total": quantity_total,
        "items_json": json.dumps(items, ensure_ascii=False),
        "raw_json": json.dumps(order, ensure_ascii=False),
        "last_synced_at": datetime.now(timezone.utc).isoformat(),
    }


def default_start(days_back):
    return (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")


def main():
    payload = read_payload()
    store_id = clean(payload.get("store_id") or os.getenv("ORDERDESK_STORE_ID"))
    api_key = clean(payload.get("api_key") or os.getenv("ORDERDESK_API_KEY"))
    timeout = int(payload.get("request_timeout") or 20)
    page_size = max(1, min(500, int(payload.get("page_size") or payload.get("limit") or 100)))
    page_count = max(1, min(100, int(payload.get("page_count") or payload.get("pages") or 30)))
    requested_records = int(payload.get("max_records") or payload.get("limit") or 0)
    max_records = max(page_size * page_count, requested_records or 0)
    max_records = max(1, min(50000, max_records))

    if not store_id or not api_key:
        print(json.dumps({
            "ok": False,
            "provider": "OrderDesk",
            "message": "Missing Order Desk credentials. Set ORDERDESK_STORE_ID and ORDERDESK_API_KEY on the backend. Do not store API keys in workflow JSON.",
            "rows": [],
        }, ensure_ascii=False, indent=2))
        return 2

    params = {
        "limit": page_size,
        "offset": max(0, int(payload.get("offset") or 0)),
        "order_by": payload.get("order_by") or "date_added",
        "order": payload.get("order") or "desc",
    }
    if payload.get("folder_id"):
        params["folder_id"] = payload["folder_id"]
    if payload.get("search_start_date"):
        params["search_start_date"] = payload["search_start_date"]
    if payload.get("search_end_date"):
        params["search_end_date"] = payload["search_end_date"]
    if payload.get("modified_start_date"):
        params["modified_start_date"] = payload["modified_start_date"]
    elif payload.get("default_modified_days_back") is not None:
        days_back = int(payload.get("default_modified_days_back") or 0)
        if days_back > 0:
            params["modified_start_date"] = default_start(days_back)
    if payload.get("modified_end_date"):
        params["modified_end_date"] = payload["modified_end_date"]

    base_url = clean(payload.get("base_url") or ORDERDESK_API_BASE).rstrip("/")
    first_source_url = ""
    orders = []
    page_offsets = []
    next_offset = params["offset"]
    pages_fetched = 0
    for page_index in range(page_count):
        if len(orders) >= max_records:
            break
        page_params = dict(params)
        page_params["offset"] = next_offset
        source_url = f"{base_url}/orders?{urlencode(page_params)}"
        if not first_source_url:
            first_source_url = source_url
        response = request_json(source_url, store_id, api_key, timeout)
        page_orders = order_list(response)
        page_offsets.append({
            "page": page_index + 1,
            "offset": next_offset,
            "limit": page_size,
            "count": len(page_orders),
        })
        if not page_orders:
            break
        pages_fetched += 1
        remaining = max_records - len(orders)
        orders.extend(page_orders[:remaining])
        if len(page_orders) < page_size or len(orders) >= max_records:
            break
        next_offset += page_size
    rows = [normalize_order(order) for order in orders]

    print(json.dumps({
        "ok": True,
        "provider": "OrderDesk",
        "source_url": first_source_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "page_size": page_size,
        "pages_requested": page_count,
        "pages_fetched": pages_fetched,
        "max_records": max_records,
        "page_offsets": page_offsets,
        "row_count": len(rows),
        "orders_count": len(orders),
        "rows": rows,
        "next_step": "Bulk import rows into CellX table cx_orderdesk_order or another mapped order table.",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
