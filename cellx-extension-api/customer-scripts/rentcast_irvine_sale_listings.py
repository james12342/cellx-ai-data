#!/usr/bin/env python3
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_BASE = "https://api.rentcast.io/v1"


def read_payload():
    raw = sys.stdin.read().strip() or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


def money(value):
    try:
        return int(float(value))
    except Exception:
        return None


def pct(current, previous):
    if current is None or previous in (None, 0):
        return None
    if current >= previous:
        return 0
    return round(((previous - current) / previous) * 100, 2)


def rentcast_get(path, params, api_key):
    url = f"{API_BASE}{path}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Api-Key": api_key,
            "User-Agent": "CellAIDataWorkflow/1.0",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
            total = response.headers.get("X-Total-Count")
            return json.loads(body), int(total) if total and total.isdigit() else None
    except HTTPError as exc:
        body = exc.read(2000).decode("utf-8", errors="replace")
        raise RuntimeError(f"RentCast API returned HTTP {exc.code}: {body}") from exc


def history_prices(history):
    prices = []
    if not isinstance(history, dict):
        return prices
    for date_key, item in sorted(history.items()):
        if not isinstance(item, dict):
            continue
        price = money(item.get("price"))
        if price:
            prices.append({"date": date_key, "price": price, "event": item.get("event") or ""})
    return prices


def price_cut_info(listing):
    current = money(listing.get("price"))
    prices = history_prices(listing.get("history"))
    previous_prices = [item["price"] for item in prices if item["price"] and item["price"] > (current or 0)]
    original = previous_prices[0] if previous_prices else current
    highest = max(previous_prices) if previous_prices else current
    previous = highest or original
    cut_amount = previous - current if current is not None and previous is not None and previous > current else 0
    return {
        "original_price": original,
        "highest_previous_price": previous,
        "price_cut_amount": cut_amount,
        "price_cut_percent": pct(current, previous),
        "history_price_count": len(prices),
        "price_history": prices,
    }


def nested_name(value):
    return value.get("name", "") if isinstance(value, dict) else ""


def nested_phone(value):
    return value.get("phone", "") if isinstance(value, dict) else ""


def nested_email(value):
    return value.get("email", "") if isinstance(value, dict) else ""


def slugify(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:90]


def normalize_listing(listing, rank, include_raw):
    cut = price_cut_info(listing)
    photos = []
    slug = slugify(listing.get("formattedAddress") or listing.get("id") or rank)
    row = {
        "rank": rank,
        "provider": "RentCast",
        "id": listing.get("id") or "",
        "formatted_address": listing.get("formattedAddress") or "",
        "address_line_1": listing.get("addressLine1") or "",
        "address_line_2": listing.get("addressLine2") or "",
        "city": listing.get("city") or "",
        "state": listing.get("state") or "",
        "zip_code": listing.get("zipCode") or "",
        "county": listing.get("county") or "",
        "latitude": listing.get("latitude"),
        "longitude": listing.get("longitude"),
        "property_type": listing.get("propertyType") or "",
        "bedrooms": listing.get("bedrooms"),
        "bathrooms": listing.get("bathrooms"),
        "square_footage": listing.get("squareFootage"),
        "lot_size": listing.get("lotSize"),
        "year_built": listing.get("yearBuilt"),
        "hoa_fee": (listing.get("hoa") or {}).get("fee") if isinstance(listing.get("hoa"), dict) else None,
        "status": listing.get("status") or "",
        "listing_type": listing.get("listingType") or "",
        "price": money(listing.get("price")),
        "original_price": cut["original_price"],
        "highest_previous_price": cut["highest_previous_price"],
        "price_cut_amount": cut["price_cut_amount"],
        "price_cut_percent": cut["price_cut_percent"],
        "listed_date": listing.get("listedDate") or "",
        "created_date": listing.get("createdDate") or "",
        "last_seen_date": listing.get("lastSeenDate") or "",
        "days_on_market": listing.get("daysOnMarket"),
        "mls_name": listing.get("mlsName") or "",
        "mls_number": listing.get("mlsNumber") or "",
        "listing_agent_name": nested_name(listing.get("listingAgent")),
        "listing_agent_phone": nested_phone(listing.get("listingAgent")),
        "listing_agent_email": nested_email(listing.get("listingAgent")),
        "listing_office_name": nested_name(listing.get("listingOffice")),
        "listing_office_phone": nested_phone(listing.get("listingOffice")),
        "listing_office_email": nested_email(listing.get("listingOffice")),
        "builder_name": nested_name(listing.get("builder")),
        "builder_development": (listing.get("builder") or {}).get("development", "") if isinstance(listing.get("builder"), dict) else "",
        "builder_phone": nested_phone(listing.get("builder")),
        "image_note": "RentCast listing schema does not expose property photos. Use MLS/IDX media or another image-licensed provider for photos.",
        "photo_1": "",
        "photo_2": "",
        "photo_3": "",
        "photo_4": "",
        "photo_5": "",
        "photos": photos,
        "landing_page_slug": slug,
        "landing_page_url": f"https://app.cellaidata.com/property/{slug}",
        "ai_summary": "",
        "ai_strengths": "",
        "ai_weaknesses": "",
        "ai_risks": "",
        "ai_recommended_buyer_profile": "",
        "ai_score": "",
        "push_status": "not_sent",
        "last_pushed_at": "",
        "price_history": cut["price_history"],
    }
    if include_raw:
        row["raw_listing"] = listing
    return row


def select_fields(row, output_fields):
    if not output_fields:
        return row
    return {field: row.get(field, "") for field in output_fields}


def fetch_sale_listings(payload, api_key):
    city = payload.get("city") or "Irvine"
    state = payload.get("state") or "CA"
    status = payload.get("status") or "Active"
    max_results = max(1, min(int(payload.get("limit") or 100), 1000))
    page_size = max(1, min(int(payload.get("page_size") or 500), 500))
    include_total = bool(payload.get("include_total_count", True))
    rows = []
    total_count = None
    offset = max(0, int(payload.get("offset") or 0))

    while len(rows) < max_results:
        params = {
            "city": city,
            "state": state,
            "status": status,
            "limit": min(page_size, max_results - len(rows)),
            "offset": offset,
        }
        if include_total:
            params["includeTotalCount"] = "true"
        for key in ("zipCode", "propertyType", "bedrooms", "bathrooms", "price", "daysOld"):
            if payload.get(key) not in (None, ""):
                params[key] = payload[key]
        page, total = rentcast_get("/listings/sale", params, api_key)
        if total is not None:
            total_count = total
        if not isinstance(page, list) or not page:
            break
        rows.extend(page)
        offset += len(page)
        if len(page) < params["limit"]:
            break
    return rows, total_count


def main():
    payload = read_payload()
    api_key_env = payload.get("api_key_env") or "RENTCAST_API_KEY"
    api_key = os.getenv(api_key_env) or os.getenv("RENTCAST_API_KEY") or ""
    min_cut_percent = float(payload.get("min_price_cut_percent") or 10)
    include_all = bool(payload.get("include_all_active_listings", True))
    include_raw = bool(payload.get("include_raw_listing", False))
    output_fields = payload.get("output_fields") or []
    customer_email = payload.get("customer_email") or ""
    errors = []
    source_rows = []
    total_count = None

    if not api_key:
        errors.append({
            "source": "rentcast",
            "error": f"Missing RentCast API key. Set {api_key_env} in the backend environment.",
        })
    else:
        try:
            source_rows, total_count = fetch_sale_listings(payload, api_key)
        except Exception as exc:
            errors.append({"source": "rentcast", "error": str(exc)})

    normalized = []
    for listing in source_rows:
        row = normalize_listing(listing, len(normalized) + 1, include_raw)
        if include_all or (row.get("price_cut_percent") is not None and row["price_cut_percent"] >= min_cut_percent):
            normalized.append(select_fields(row, output_fields))

    mode = "all_active_listings" if include_all else "price_cut_filter"
    city = payload.get("city") or "Irvine"
    state = payload.get("state") or "CA"
    if include_all:
        subject = f"{city}, {state} active sale listings: {len(normalized)} home(s)"
        summary = f"Found {len(normalized)} active sale listing(s) from RentCast for {city}, {state}."
    else:
        subject = f"{city}, {state} price-cut listings: {len(normalized)} home(s) at {min_cut_percent:.0f}%+"
        summary = f"Found {len(normalized)} active listing(s) with estimated price cuts of {min_cut_percent:.0f}% or more."

    lines = ["Hi,", "", summary, ""]
    for row in normalized[:12]:
        price = f"${row['price']:,}" if row.get("price") else "price unavailable"
        cut = f"cut {row['price_cut_percent']}%" if row.get("price_cut_percent") else "no price cut"
        lines.append(
            f"- {row.get('formatted_address')} | {price} | {cut} | "
            f"{row.get('bedrooms')} bd / {row.get('bathrooms')} ba | MLS {row.get('mls_number') or 'n/a'}"
        )
    lines.extend(["", "Full structured listing data is available in the workflow output."])

    print(json.dumps({
        "ok": bool(normalized),
        "provider": "RentCast",
        "source_url": "https://api.rentcast.io/v1/listings/sale",
        "mode": mode,
        "city": city,
        "state": state,
        "status": payload.get("status") or "Active",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "include_all_active_listings": include_all,
        "min_price_cut_percent": min_cut_percent,
        "total_count": total_count,
        "row_count": len(normalized),
        "rows": normalized,
        "email": {"to": customer_email, "subject": subject, "body": "\n".join(lines)},
        "errors": errors,
        "next_step": "Send email.body through the Gmail node, export rows to Excel, or map fields into CellX tables.",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
