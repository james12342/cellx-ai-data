#!/usr/bin/env python3
import html
import getpass
import json
import re
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen


SAMPLE_ROWS = [
    {
        "rank": 1,
        "category": "Kitchen & Dining",
        "asin": "B0BZYCJK89",
        "sku": "B0BZYCJK89",
        "title": "Owala FreeSip Stainless Steel Water Bottle 24 oz Denim",
        "brand": "Owala",
        "price": 29.99,
        "rating": 4.6,
        "reviews": 135830,
        "estimated_demand": "Very high",
        "product_url": "https://www.amazon.com/dp/B0BZYCJK89",
        "notes": "Demo fallback row. Seller SKU requires Amazon SP-API.",
    },
    {
        "rank": 2,
        "category": "Kitchen & Dining",
        "asin": "B0CQVWT2NH",
        "sku": "B0CQVWT2NH",
        "title": "HydroJug Traveler 40oz Insulated Tumbler",
        "brand": "HydroJug",
        "price": 31.99,
        "rating": 4.6,
        "reviews": 17171,
        "estimated_demand": "High",
        "product_url": "https://www.amazon.com/dp/B0CQVWT2NH",
        "notes": "Demo fallback row. Seller SKU requires Amazon SP-API.",
    },
    {
        "rank": 3,
        "category": "Kitchen & Dining",
        "asin": "B0113UZJE2",
        "sku": "B0113UZJE2",
        "title": "Etekcity Food Kitchen Scale, Digital Grams and Ounces",
        "brand": "Etekcity",
        "price": 13.99,
        "rating": 4.6,
        "reviews": 176781,
        "estimated_demand": "Very high",
        "product_url": "https://www.amazon.com/dp/B0113UZJE2",
        "notes": "Demo fallback row. Seller SKU requires Amazon SP-API.",
    },
]


def read_payload():
    raw = sys.stdin.read().strip() or "{}"
    try:
      return json.loads(raw)
    except Exception:
      return {}


def number(value):
    try:
        return float(str(value).replace("$", "").replace(",", ""))
    except Exception:
        return None


def estimate(rank, reviews):
    reviews = int(reviews or 0)
    if rank <= 3 and reviews >= 100000:
        return "Very high"
    if rank <= 10 and reviews >= 10000:
        return "High"
    return "Medium"


def brand_from_title(title):
    match = re.search(r"\b(Owala|HydroJug|Etekcity|Stanley|Amazon Basics|Apple|Bounty|Neutrogena)\b", title, re.I)
    if match:
        return match.group(1)
    return " ".join(title.split()[:2])


def scrape_public_page(url, limit):
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    page = urlopen(req, timeout=12).read().decode("utf-8", errors="ignore")
    chunks = re.split(r'data-asin="([A-Z0-9]{10})"', page)
    rows = []
    for idx in range(1, len(chunks), 2):
        asin = chunks[idx]
        block = chunks[idx + 1][:7000]
        text = html.unescape(re.sub(r"<[^>]+>", " ", block))
        text = re.sub(r"\s+", " ", text).strip()
        rank_match = re.search(r"#(\d+)", text)
        title_match = re.search(r"#\d+\s+(.+?)\s+\d(?:\.\d)? out of 5 stars", text)
        rating_match = re.search(r"(\d(?:\.\d)?) out of 5 stars", text)
        reviews_match = re.search(r"out of 5 stars\s+((?:\d{1,3},)*\d{2,})", text)
        price_match = re.search(r"\$(\d+(?:\.\d{2})?)", text)
        href_match = re.search(r'href="([^"]*/dp/' + re.escape(asin) + r'[^"]*)"', block)
        if not rank_match or not title_match:
            continue
        rank = int(rank_match.group(1))
        title = title_match.group(1).strip()
        reviews = int((reviews_match.group(1) if reviews_match else "0").replace(",", ""))
        rows.append({
            "rank": rank,
            "category": "Amazon Best Sellers",
            "asin": asin,
            "sku": asin,
            "title": title,
            "brand": brand_from_title(title),
            "price": number(price_match.group(1) if price_match else ""),
            "rating": number(rating_match.group(1) if rating_match else ""),
            "reviews": reviews,
            "estimated_demand": estimate(rank, reviews),
            "product_url": "https://www.amazon.com" + html.unescape(href_match.group(1)).split("?")[0] if href_match else f"https://www.amazon.com/dp/{asin}",
            "notes": "Captured from public Amazon page. Seller SKU requires Amazon SP-API.",
        })
        if len(rows) >= limit:
            break
    return rows


def main():
    payload = read_payload()
    source_url = payload.get("source_url") or "https://www.amazon.com/Best-Sellers/zgbs"
    limit = int(payload.get("limit") or 10)
    limit = max(1, min(limit, 25))
    scraped_at = datetime.now(timezone.utc).isoformat()
    used_fallback = False
    error = None

    try:
        rows = scrape_public_page(source_url, limit)
    except Exception as exc:
        rows = []
        error = str(exc)

    if not rows:
        used_fallback = True
        rows = SAMPLE_ROWS[:limit]

    print(json.dumps({
        "ok": True,
        "source_url": source_url,
        "scraped_at": scraped_at,
        "runtime_user": getpass.getuser(),
        "used_fallback": used_fallback,
        "error": error,
        "row_count": len(rows),
        "rows": rows,
        "next_step": "Feed rows into JSON Transform, Excel Export, or ChatGPT supplier analysis.",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
