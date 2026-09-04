#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


ORDERDESK_API_BASE = "https://app.orderdesk.me/api"


def read_payload():
    raw = sys.stdin.read().strip() or "{}"
    try:
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


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
        "User-Agent": f"CellAIData-OrderDesk-Workflow/1.0 ({store_id}; https://cellaidata.com)",
    }
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset, errors="replace"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1000]
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


def order_items(order):
    items = as_list(pick(order, "order_items", "items", "line_items"))
    rows = []
    for item in items:
        rows.append({
            "sku": clean_text(pick(item, "sku", "code", "variation_id")),
            "name": clean_text(pick(item, "name", "product_name", "title")),
            "quantity": pick(item, "quantity", "qty") or 1,
            "price": pick(item, "price", "unit_price", "total"),
        })
    return rows


def ship_to_address(order):
    return {
        "name": clean_text(pick(order, "shipping.name", "customer.name", "name")),
        "first_name": clean_text(pick(order, "shipping.first_name", "customer.first_name", "first_name")),
        "last_name": clean_text(pick(order, "shipping.last_name", "customer.last_name", "last_name")),
        "company": clean_text(pick(order, "shipping.company", "company")),
        "address1": clean_text(pick(order, "shipping.address1", "shipping.address_1", "address1")),
        "address2": clean_text(pick(order, "shipping.address2", "shipping.address_2", "address2")),
        "city": clean_text(pick(order, "shipping.city", "city")),
        "state": clean_text(pick(order, "shipping.state", "state")),
        "postal_code": clean_text(pick(order, "shipping.postal_code", "shipping.zip", "zip")),
        "country": clean_text(pick(order, "shipping.country", "country") or "US"),
        "phone": clean_text(pick(order, "shipping.phone", "customer.phone", "phone")),
        "email": clean_text(pick(order, "email", "customer.email", "shipping.email")),
    }


def requested_shipping(order):
    candidates = [
        "shipping_method",
        "shipping.method",
        "shipping_description",
        "checkout_shipping_title",
        "ship_method",
        "carrier",
    ]
    parts = [clean_text(pick(order, path)) for path in candidates]
    metadata = order.get("metadata") if isinstance(order.get("metadata"), dict) else {}
    for key in ("shipping_method", "ship_method", "carrier", "requested_service"):
        parts.append(clean_text(metadata.get(key)))
    return " ".join(part for part in parts if part)


def detect_carrier(order, rules):
    source = requested_shipping(order)
    haystack = (source + " " + json.dumps(order, ensure_ascii=False)).lower()
    for carrier, tokens in rules.items():
        for token in tokens:
            if token.lower() in haystack:
                return carrier.upper(), source or token
    return "MANUAL_REVIEW", source


def normalize_order(order, rank, carrier_rules, default_package, ship_from):
    carrier, service_hint = detect_carrier(order, carrier_rules)
    orderdesk_id = clean_text(pick(order, "id", "order_id", "orderdesk_id"))
    public_order_id = clean_text(pick(order, "source_id", "order_number", "order_id", "id"))
    ship_to = ship_to_address(order)
    customer_name = " ".join(part for part in [ship_to.get("first_name"), ship_to.get("last_name")] if part).strip()
    if not customer_name:
        customer_name = ship_to.get("name")
    return {
        "rank": rank,
        "orderdesk_order_id": orderdesk_id,
        "order_id": public_order_id,
        "customer_id": clean_text(pick(order, "customer_id", "source_name")),
        "customer_name": customer_name,
        "customer_email": clean_text(pick(order, "email", "customer.email", "shipping.email")),
        "total": pick(order, "total", "order_total", "grand_total"),
        "quantity": pick(order, "quantity", "qty", "item_count"),
        "order_date": clean_text(pick(order, "date_added", "order_date", "date")),
        "updated_date": clean_text(pick(order, "date_updated", "updated_date")),
        "requested_shipping": requested_shipping(order),
        "carrier": carrier,
        "service_hint": service_hint,
        "route_status": "ready_for_label" if carrier in ("UPS", "FEDEX") else "manual_review",
        "action": "create_shipment_payload" if carrier in ("UPS", "FEDEX") else "review_shipping_method",
        "ship_from": ship_from,
        "ship_to": ship_to,
        "items": order_items(order),
        "package": default_package,
        "carrier_payload": {
            "carrier": carrier,
            "order_id": public_order_id,
            "reference": orderdesk_id,
            "service_hint": service_hint,
            "ship_from": ship_from,
            "ship_to": ship_to,
            "package": default_package,
            "items": order_items(order),
        },
    }


def main():
    payload = read_payload()
    store_id = clean_text(payload.get("store_id") or os.getenv("ORDERDESK_STORE_ID"))
    api_key = clean_text(payload.get("api_key") or os.getenv("ORDERDESK_API_KEY"))
    timeout = int(payload.get("request_timeout") or 20)
    limit = max(1, min(500, int(payload.get("limit") or 25)))
    dry_run = bool(payload.get("dry_run", True))

    if not store_id or not api_key:
        print(json.dumps({
            "ok": False,
            "provider": "OrderDesk",
            "message": "Missing Order Desk credentials. Set ORDERDESK_STORE_ID and ORDERDESK_API_KEY on the backend, or provide store_id/api_key in the script node input JSON.",
            "rows": [],
        }, ensure_ascii=False, indent=2))
        return 2

    params = {
        "limit": limit,
        "offset": max(0, int(payload.get("offset") or 0)),
    }
    for key in ("folder_id", "search_start_date", "search_end_date", "modified_start_date", "modified_end_date", "order_by", "order"):
        if payload.get(key):
            params[key] = payload[key]

    base_url = clean_text(payload.get("base_url") or ORDERDESK_API_BASE).rstrip("/")
    source_url = f"{base_url}/orders?{urlencode(params)}"
    response = request_json(source_url, store_id, api_key, timeout)
    orders = order_list(response)

    carrier_rules = payload.get("carrier_rules") or {
        "ups": ["ups", "united parcel", "ground saver"],
        "fedex": ["fedex", "federal express", "home delivery"],
    }
    default_package = payload.get("default_package") or {
        "weight_lbs": 1,
        "length_in": 10,
        "width_in": 8,
        "height_in": 4,
    }
    ship_from = payload.get("ship_from") or {
        "name": "Warehouse",
        "country": "US",
    }

    rows = [
        normalize_order(order, index + 1, carrier_rules, default_package, ship_from)
        for index, order in enumerate(orders[:limit])
    ]

    ups_rows = [row for row in rows if row["carrier"] == "UPS"]
    fedex_rows = [row for row in rows if row["carrier"] == "FEDEX"]
    manual_rows = [row for row in rows if row["carrier"] == "MANUAL_REVIEW"]

    print(json.dumps({
        "ok": True,
        "provider": "OrderDesk",
        "source_url": source_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "message": "Fetched Order Desk orders and prepared UPS/FedEx shipment payloads. Dry run is on, so no label was purchased or order was mutated.",
        "orders_count": len(orders),
        "row_count": len(rows),
        "ups_count": len(ups_rows),
        "fedex_count": len(fedex_rows),
        "manual_review_count": len(manual_rows),
        "rows": rows,
        "ups_rows": ups_rows,
        "fedex_rows": fedex_rows,
        "manual_review_rows": manual_rows,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
