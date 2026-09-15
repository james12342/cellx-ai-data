#!/usr/bin/env python3
import json
import math
import sys
from datetime import datetime, timezone


SAMPLE_ROWS = [
    {
        "platform": "TikTok Shop",
        "product_id": "tt_sample_1001",
        "title": "Portable Mini Thermal Label Printer",
        "category": "Office Supplies",
        "price": 29.99,
        "sales_count": 18420,
        "review_count": 2910,
        "rating": 4.7,
        "gmv": 552415.8,
        "url": "https://www.tiktok.com/shop",
        "source": "sample",
    },
    {
        "platform": "FB Marketplace",
        "product_id": "fb_sample_2001",
        "title": "Foldable Storage Ottoman Bench",
        "category": "Home",
        "price": 42.0,
        "views": 12800,
        "saves": 640,
        "messages": 96,
        "sold_count": 18,
        "url": "https://www.facebook.com/marketplace/",
        "source": "sample",
    },
]


def read_payload():
    raw = sys.stdin.read().strip() or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


def num(value, default=0.0):
    if value is None:
        return default
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except Exception:
        return default


def text(row, *keys, default=""):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def first_number(row, keys, default=0.0):
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return num(row.get(key), default)
    return default


def estimate_fb_sales(row):
    sold = first_number(row, ["sold_count", "sales_count", "units_sold"], None)
    if sold is not None:
        return sold, "reported"

    views = first_number(row, ["views", "view_count", "impressions"])
    saves = first_number(row, ["saves", "save_count", "favorites", "likes"])
    messages = first_number(row, ["messages", "message_count", "seller_contacts"])

    # Marketplace does not expose public unit sales through an official broad API.
    # This conservative estimate treats messages as the strongest buying intent.
    estimate = messages * 0.22 + saves * 0.035 + views * 0.0015
    return round(max(0, estimate), 1), "estimated_from_engagement"


def normalize_row(row):
    raw_platform = text(row, "platform", "source_platform", "channel", default="").lower()
    is_tiktok = "tiktok" in raw_platform or "product_sold_count" in row
    platform = "TikTok Shop" if is_tiktok else "FB Marketplace"

    if platform == "TikTok Shop":
        sales_count = first_number(row, ["sales_count", "sold_count", "product_sold_count", "units_sold"])
        sales_type = "reported" if sales_count else "missing"
    else:
        sales_count, sales_type = estimate_fb_sales(row)

    price = first_number(row, ["price", "product_price", "sale_price"])
    reviews = first_number(row, ["review_count", "reviews", "product_review_count"])
    rating = first_number(row, ["rating", "product_rating"])
    views = first_number(row, ["views", "view_count", "impressions"])
    saves = first_number(row, ["saves", "save_count", "favorites", "likes"])
    messages = first_number(row, ["messages", "message_count", "seller_contacts"])
    gmv = first_number(row, ["gmv", "revenue", "gross_sales"], sales_count * price if price else 0)

    hot_score = (
        math.log1p(sales_count) * 42
        + math.log1p(gmv) * 12
        + math.log1p(reviews) * 9
        + math.log1p(views) * 5
        + math.log1p(saves) * 6
        + math.log1p(messages) * 11
        + max(0, rating - 3.5) * 10
    )

    confidence = "high" if sales_type == "reported" else "medium"
    if platform == "FB Marketplace" and sales_type != "reported":
        confidence = "low"

    return {
        "platform": platform,
        "product_id": text(row, "product_id", "id", "listing_id", "sku"),
        "title": text(row, "title", "product_name", "name", default="Untitled product"),
        "category": text(row, "category", "product_category"),
        "price": round(price, 2) if price else None,
        "sales_count": sales_count,
        "sales_type": sales_type,
        "gmv": round(gmv, 2) if gmv else None,
        "review_count": int(reviews) if reviews else 0,
        "rating": rating or None,
        "views": int(views) if views else 0,
        "saves": int(saves) if saves else 0,
        "messages": int(messages) if messages else 0,
        "hot_score": round(hot_score, 2),
        "confidence": confidence,
        "url": text(row, "url", "product_url", "listing_url"),
        "source": text(row, "source", "data_source", default="input"),
    }


def collect_rows(payload):
    rows = []
    for key in ("rows", "products", "items", "listings"):
        if isinstance(payload.get(key), list):
            rows.extend(payload[key])

    for source in payload.get("sources", []) if isinstance(payload.get("sources"), list) else []:
        if isinstance(source, dict):
            source_name = source.get("name") or source.get("platform") or "source"
            for row in source.get("rows", []):
                if isinstance(row, dict):
                    merged = dict(row)
                    merged.setdefault("source", source_name)
                    merged.setdefault("platform", source.get("platform"))
                    rows.append(merged)
    return [row for row in rows if isinstance(row, dict)]


def main():
    payload = read_payload()
    limit = int(payload.get("limit") or 25)
    limit = max(1, min(limit, 100))
    rows = collect_rows(payload) or SAMPLE_ROWS
    normalized = [normalize_row(row) for row in rows]
    ranked = sorted(normalized, key=lambda row: row["hot_score"], reverse=True)[:limit]

    print(json.dumps({
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(ranked),
        "method": "Rank by reported TikTok sales when available; estimate FB Marketplace demand from seller-provided/exported engagement when sales are unavailable.",
        "data_warning": "FB Marketplace does not provide broad public product-sales data through an official Marketplace API. Treat FB sales_count as reported only when supplied by your own seller/export source; otherwise it is an estimate.",
        "rows": ranked,
        "next_step": "Export rows to Excel/Sheets, then have AI shortlist products by hot_score, confidence, margin, competition, and sourcing risk.",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
