#!/usr/bin/env python3
import html
import json
import re
import sys
from datetime import datetime, timezone
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


DEFAULT_URL = "https://www.zillow.com/homes/Irvine,-CA_rb/"


def read_payload():
    raw = sys.stdin.read().strip() or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


def fetch_text(url):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.zillow.com/",
        },
    )
    with urlopen(request, timeout=25) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read(4_000_000).decode(charset, errors="replace")


def clean_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    text = text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def as_int(value):
    value = clean_number(value)
    return int(value) if value is not None else None


def build_search_url(location):
    if not location:
        return DEFAULT_URL
    slug = quote_plus(str(location).replace(",", "")).replace("+", "-")
    return f"https://www.zillow.com/homes/{slug}_rb/"


def json_candidates(page_html):
    page_html = html.unescape(page_html)
    for pattern in [
        r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        r'<script[^>]+id="hdpApolloPreloadedData"[^>]*>(.*?)</script>',
        r'<script[^>]+type="application/json"[^>]*>(.*?)</script>',
    ]:
        for match in re.finditer(pattern, page_html, flags=re.I | re.S):
            text = match.group(1).strip()
            if not text:
                continue
            try:
                data = json.loads(text)
                if isinstance(data, str):
                    data = json.loads(data)
                yield data
            except Exception:
                continue

    for key in ("searchResults", "cat1", "property", "homeInfo"):
        index = page_html.find(f'"{key}"')
        if index == -1:
            continue
        start = page_html.rfind("{", 0, index)
        if start == -1:
            continue
        snippet = page_html[start:start + 1_500_000]
        depth = 0
        end = None
        in_string = False
        escape_next = False
        for offset, char in enumerate(snippet):
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = offset + 1
                    break
        if end:
            try:
                yield json.loads(snippet[:end])
            except Exception:
                continue


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def collect_listings(data):
    listings = []
    seen = set()
    for item in walk(data):
        home = item.get("homeInfo") if isinstance(item.get("homeInfo"), dict) else item
        zpid = home.get("zpid") or home.get("id")
        detail_url = home.get("detailUrl") or home.get("hdpUrl")
        address = home.get("address") or home.get("streetAddress")
        price = home.get("price") or home.get("unformattedPrice")
        if not (zpid or detail_url) or not (address or price):
            continue
        key = str(zpid or detail_url)
        if key in seen:
            continue
        seen.add(key)
        listings.append(home)
    return listings


def absolute_zillow_url(url):
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return "https://www.zillow.com" + url


def price_cut_amount(home):
    candidates = [
        home.get("priceReduction"),
        home.get("priceReductionString"),
        home.get("priceChange"),
        home.get("priceChangeAmount"),
    ]
    for value in candidates:
        if value in (None, "", 0):
            continue
        amount = clean_number(value)
        if amount:
            return abs(amount)
    return None


def collect_photos(home):
    photos = []
    for key in ("imgSrc", "image", "largeImage"):
        if isinstance(home.get(key), str) and home[key].startswith("http"):
            photos.append(home[key])
    for photo in home.get("carouselPhotos") or home.get("photos") or []:
        if isinstance(photo, dict):
            url = photo.get("url") or photo.get("mixedSources", {}).get("jpeg", [{}])[-1].get("url")
            if url and url.startswith("http"):
                photos.append(url)
    deduped = []
    for url in photos:
        if url not in deduped:
            deduped.append(url)
    return deduped[:12]


def normalize_listing(home, rank):
    price = as_int(home.get("unformattedPrice") or home.get("price"))
    cut_amount = price_cut_amount(home)
    previous_price = price + int(cut_amount) if price is not None and cut_amount is not None else None
    cut_percent = round((cut_amount / previous_price) * 100, 2) if previous_price else None
    detail_url = absolute_zillow_url(home.get("detailUrl") or home.get("hdpUrl") or "")
    lat_long = home.get("latLong") or {}
    return {
        "rank": rank,
        "zpid": str(home.get("zpid") or home.get("id") or ""),
        "address": home.get("address") or home.get("streetAddress") or "",
        "city": home.get("city") or "",
        "state": home.get("state") or "CA",
        "zipcode": str(home.get("zipcode") or ""),
        "price": price,
        "previous_price_estimate": previous_price,
        "price_cut_amount": int(cut_amount) if cut_amount is not None else None,
        "price_cut_percent": cut_percent,
        "beds": clean_number(home.get("beds") or home.get("bedrooms")),
        "baths": clean_number(home.get("baths") or home.get("bathrooms")),
        "living_area_sqft": as_int(home.get("livingArea") or home.get("area")),
        "lot_area": home.get("lotAreaString") or "",
        "home_type": home.get("homeType") or "",
        "status": home.get("homeStatus") or home.get("statusText") or "",
        "days_on_zillow": as_int(home.get("daysOnZillow")),
        "broker_name": home.get("brokerName") or "",
        "latitude": lat_long.get("latitude") or home.get("latitude"),
        "longitude": lat_long.get("longitude") or home.get("longitude"),
        "detail_url": detail_url,
        "primary_image": (collect_photos(home) or [""])[0],
        "photos": collect_photos(home),
    }


def enrich_detail(row):
    if not row.get("detail_url"):
        return row
    try:
        detail_html = fetch_text(row["detail_url"])
    except Exception as exc:
        row["detail_error"] = str(exc)
        return row
    for data in json_candidates(detail_html):
        for item in walk(data):
            if not isinstance(item, dict):
                continue
            if str(item.get("zpid") or "") == row.get("zpid"):
                photos = collect_photos(item)
                if photos:
                    row["photos"] = photos
                    row["primary_image"] = photos[0]
                row["description"] = item.get("description") or item.get("postingProductType") or row.get("description", "")
                row["year_built"] = as_int(item.get("yearBuilt") or row.get("year_built"))
                row["property_tax_rate"] = item.get("propertyTaxRate") or row.get("property_tax_rate")
                row["rent_zestimate"] = as_int(item.get("rentZestimate") or row.get("rent_zestimate"))
                return row
    return row


def main():
    payload = read_payload()
    source_url = payload.get("source_url") or build_search_url(payload.get("location") or "Irvine, CA")
    limit = max(1, min(int(payload.get("limit") or 25), 100))
    detail_limit = max(0, min(int(payload.get("detail_limit") or 8), limit))
    min_cut_percent = float(payload.get("min_price_cut_percent") or 10)
    include_all = bool(payload.get("include_all_active_listings"))
    mode = "all_active_listings" if include_all else "price_cut_filter"

    errors = []
    rows = []
    try:
        page_html = fetch_text(source_url)
        all_listings = []
        for data in json_candidates(page_html):
            all_listings.extend(collect_listings(data))
        deduped = []
        seen = set()
        for home in all_listings:
            key = str(home.get("zpid") or home.get("detailUrl") or home.get("hdpUrl"))
            if key not in seen:
                seen.add(key)
                deduped.append(home)

        for home in deduped:
            row = normalize_listing(home, len(rows) + 1)
            if include_all or (row["price_cut_percent"] is not None and row["price_cut_percent"] >= min_cut_percent):
                rows.append(row)
            if len(rows) >= limit:
                break

        for index, row in enumerate(rows[:detail_limit]):
            rows[index] = enrich_detail(row)
    except Exception as exc:
        errors.append({"source": "zillow_public_page", "error": str(exc)})

    if include_all:
        email_subject = f"Irvine CA Zillow active listings: {len(rows)} home(s)"
        summary_line = f"Found {len(rows)} Irvine, CA Zillow active sale listing(s)."
    else:
        email_subject = f"Irvine CA Zillow price-cut homes: {len(rows)} listing(s) at {min_cut_percent:.0f}%+ reduction"
        summary_line = f"Found {len(rows)} Irvine, CA Zillow listing(s) with estimated price cuts of {min_cut_percent:.0f}% or more."
    email_lines = [
        "Hi,",
        "",
        summary_line,
        "",
    ]
    for row in rows[:10]:
        cut_text = f"cut {row.get('price_cut_percent')}%" if row.get("price_cut_percent") is not None else "no price-cut data"
        email_lines.append(
            f"- {row.get('address')} | ${row.get('price'):,} | "
            f"{cut_text} | {row.get('beds')} bd / {row.get('baths')} ba | {row.get('detail_url')}"
        )
    if not rows and not errors:
        errors.append({
            "source": "zillow_public_page",
            "error": "No embedded listing data was found. Zillow may have served a JavaScript-only page or blocked automated access.",
        })
    email_lines.extend(["", "Full structured rows and image URLs are attached in the workflow output."])

    print(json.dumps({
        "ok": bool(rows),
        "source_url": source_url,
        "source": "zillow_public_page",
        "mode": mode,
        "location": payload.get("location") or "Irvine, CA",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "include_all_active_listings": include_all,
        "min_price_cut_percent": min_cut_percent,
        "row_count": len(rows),
        "rows": rows,
        "email": {
            "subject": email_subject,
            "body": "\n".join(email_lines),
            "to": payload.get("customer_email") or "",
        },
        "errors": errors,
        "next_step": "Review rows, export to Excel, or pass email.subject/body to a Gmail or Outlook workflow node.",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
