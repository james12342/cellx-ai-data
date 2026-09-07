#!/usr/bin/env python3
import html
import json
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_SOURCE_URL = "https://www.askfred.net/tournaments"
BASE_URL = "https://www.askfred.net"


def read_payload():
    raw = sys.stdin.read().strip() or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


def fetch_html(url):
    request = Request(
        url,
        headers={
            "User-Agent": "CellAIDataWorkflowDemo/1.0 (+https://www.cellaidata.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": BASE_URL,
        },
    )
    with urlopen(request, timeout=25) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read(2_000_000).decode(charset, errors="replace")


def clean_text(value):
    value = re.sub(r"<(script|style).*?</\1>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def extract_date(text):
    patterns = [
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b",
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(0)
    return ""


def extract_location(text):
    match = re.search(r"\b([A-Z][A-Za-z .'-]{2,40}),\s*(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|MA|MD|ME|MI|MN|MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VA|VT|WA|WI|WV|WY)\b", text)
    if match:
        return f"{match.group(1).strip()}, {match.group(2)}"
    return ""


def detect_weapon(text):
    found = []
    for weapon in ("foil", "epee", "saber", "sabre"):
        if re.search(rf"\b{weapon}\b", text, flags=re.I):
            found.append("saber" if weapon == "sabre" else weapon)
    return ", ".join(dict.fromkeys(found))


def classify_level(text):
    lower = text.lower()
    d1_terms = [
        "division i", "div i", "div 1", "d1", "nac", "national",
        "championship", "junior olympic", "fie", "world cup", "satellite",
    ]
    advanced_terms = [
        "division ia", "div ia", "div 1a", "roc", "rjcc", "ryc", "syc",
        "regional", "open", "a-rated", "a rated", "b-rated", "b rated",
    ]
    beginner_terms = [
        "beginner", "novice", "unrated", "y8", "y10", "y12", "y14",
        "e and under", "e & under", "d and under", "d & under", "youth",
        "learn to fence", "developmental",
    ]
    intermediate_terms = [
        "division ii", "div ii", "div 2", "division iii", "div iii",
        "div 3", "c and under", "c & under", "senior mixed",
    ]
    if any(term in lower for term in d1_terms):
        return "D1 / Elite", "d1-elite", "National, Division I, or elite signal in title/details."
    if any(term in lower for term in beginner_terms):
        return "Beginner", "beginner", "Beginner, youth, novice, or unrated signal in title/details."
    if any(term in lower for term in intermediate_terms):
        return "Intermediate", "intermediate", "Div II/III or C-and-under style signal in title/details."
    if any(term in lower for term in advanced_terms):
        return "Advanced", "advanced", "Open, regional, or rated-event signal in title/details."
    return "Intermediate", "intermediate", "No explicit level found; placed in intermediate review bucket."


def infer_rating_hint(text):
    hints = []
    for pattern in (r"\b[A-E]\s*(?:&|and)\s*Under\b", r"\bUnrated\b", r"\bNovice\b", r"\bDiv(?:ision)?\s*(?:I|II|III|1|2|3|1A|IA)\b"):
        for match in re.finditer(pattern, text, flags=re.I):
            hints.append(match.group(0))
    return ", ".join(dict.fromkeys(hints))


def parse_tournaments(page_html, source_url, limit):
    rows = []
    seen = set()
    link_pattern = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', flags=re.I | re.S)
    ignored_titles = {
        "reset", "download as csv", "download ical", "google calendar",
        "outlook.com", "office 365", "tournaments", "next", "previous", "last",
    }
    for match in link_pattern.finditer(page_html):
        href, label_html = match.groups()
        if not re.search(r"/tournaments/[0-9a-f-]{20,}", href, flags=re.I):
            continue
        if re.search(r"\.(ics|csv)(?:$|[?#])", href, flags=re.I):
            continue
        title = clean_text(label_html)
        title_key = re.sub(r"\s+", " ", title.lower()).strip(" \u00bb\u203a")
        if len(title) < 4 or title_key in ignored_titles or title_key in {"details", "view", "more"}:
            continue
        url = urljoin(source_url, href)
        key = (title.lower(), url)
        if key in seen:
            continue
        seen.add(key)
        context = page_html[max(0, match.start() - 1200): min(len(page_html), match.end() + 1600)]
        context_text = clean_text(context)
        level, page_slug, reason = classify_level(title)
        rows.append({
            "rank": len(rows) + 1,
            "page_slug": page_slug,
            "page_title": f"{level} Fencer Tournaments",
            "level": level,
            "title": title,
            "start_date": extract_date(context_text),
            "location": extract_location(context_text),
            "weapon": detect_weapon(context_text),
            "rating_hint": infer_rating_hint(context_text),
            "tournament_url": url,
            "source_url": source_url,
            "why_this_level": reason,
            "notes": "Parsed from public AskFRED tournament page.",
        })
        if len(rows) >= limit:
            break
    return rows


def sample_rows():
    samples = [
        ("Beginner Foil and Epee Developmental", "Beginner", "beginner", "Irvine, CA", "foil, epee", "Unrated / youth friendly"),
        ("SoCal Div III Mixed Saber", "Intermediate", "intermediate", "Los Angeles, CA", "saber", "Div III"),
        ("Regional Open Circuit Epee", "Advanced", "advanced", "San Diego, CA", "epee", "ROC / open"),
        ("Division I National Qualifier", "D1 / Elite", "d1-elite", "Anaheim, CA", "foil, epee, saber", "Division I"),
    ]
    rows = []
    for index, (title, level, slug, location, weapon, hint) in enumerate(samples, start=1):
        rows.append({
            "rank": index,
            "page_slug": slug,
            "page_title": f"{level} Fencer Tournaments",
            "level": level,
            "title": title,
            "start_date": "",
            "location": location,
            "weapon": weapon,
            "rating_hint": hint,
            "tournament_url": DEFAULT_SOURCE_URL,
            "source_url": DEFAULT_SOURCE_URL,
            "why_this_level": "Sample fallback row for demo when the live page cannot be parsed.",
            "notes": "Sample fallback. Replace with live AskFRED rows when available.",
        })
    return rows


def build_pages(rows):
    order = ["Beginner", "Intermediate", "Advanced", "D1 / Elite"]
    pages = []
    for level in order:
        page_rows = [row for row in rows if row["level"] == level]
        slug = "d1-elite" if level == "D1 / Elite" else level.lower().replace(" ", "-")
        pages.append({
            "page_slug": slug,
            "page_title": f"{level} Fencer Tournaments",
            "level": level,
            "row_count": len(page_rows),
            "rows": page_rows,
        })
    return pages


def main():
    payload = read_payload()
    source_url = payload.get("source_url") or DEFAULT_SOURCE_URL
    limit = max(1, min(int(payload.get("limit") or 80), 200))
    fallback_sample = bool(payload.get("fallback_sample", True))
    errors = []
    rows = []
    mode = "live"

    try:
        page_html = fetch_html(source_url)
        rows = parse_tournaments(page_html, source_url, limit)
    except Exception as exc:
        errors.append({"source": source_url, "error": str(exc)})

    if not rows and fallback_sample:
        rows = sample_rows()[:limit]
        mode = "sample_fallback"

    print(json.dumps({
        "ok": bool(rows),
        "provider": "AskFRED",
        "source_url": source_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "row_count": len(rows),
        "page_count": len([page for page in build_pages(rows) if page["row_count"]]),
        "pages": build_pages(rows),
        "rows": rows,
        "errors": errors,
        "next_step": "Export rows to Excel or map each level to CellX pages: Beginner, Intermediate, Advanced, and D1 / Elite.",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
