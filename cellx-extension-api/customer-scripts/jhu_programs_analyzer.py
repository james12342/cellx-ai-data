#!/usr/bin/env python3
import html
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_SOURCE_URL = "https://e-catalogue.jhu.edu/programs/"
BASE_URL = "https://e-catalogue.jhu.edu"

DIVISIONS = [
    "Bloomberg School of Public Health",
    "Carey Business School",
    "Krieger School of Arts and Sciences",
    "Peabody Institute",
    "School of Advanced International Studies",
    "School of Education",
    "School of Medicine",
    "School of Nursing",
    "Whiting School of Engineering",
]

HIGH_DEMAND_KEYWORDS = {
    "ai_data_technology": [
        "artificial intelligence", "data science", "computer", "analytics",
        "information systems", "machine learning", "robotics", "cyber",
    ],
    "health_biomedical": [
        "public health", "medicine", "biomedical", "biotechnology",
        "nursing", "epidemiology", "biostatistics", "mental health",
        "clinical", "healthcare", "health care",
    ],
    "business_policy_global": [
        "business", "finance", "marketing", "management", "economics",
        "international relations", "public policy", "security", "real estate",
    ],
    "engineering_science": [
        "engineering", "applied physics", "environmental", "systems",
        "materials", "mechanical", "electrical", "chemical",
    ],
}


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._active_href = None
        self._active_text = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attrs = dict(attrs)
        href = attrs.get("href")
        if href:
            self._active_href = href
            self._active_text = []

    def handle_endtag(self, tag):
        if tag == "a" and self._active_href:
            text = clean_text(" ".join(self._active_text))
            if text:
                self.links.append({"href": self._active_href, "text": text})
            self._active_href = None
            self._active_text = []

    def handle_data(self, data):
        if self._active_href:
            self._active_text.append(data)


def read_payload():
    raw = sys.stdin.read().strip() or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


def clean_text(value):
    value = html.unescape(value or "")
    value = value.replace("\u200b", "").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", value).strip()


def fetch_html(url, timeout):
    request = Request(
        url,
        headers={
            "User-Agent": "CellAIDataWorkflowDemo/1.0 (+https://www.cellaidata.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read(3_000_000).decode(charset, errors="replace")


def degree_level(name):
    lower = name.lower()
    if any(term in lower for term in ["phd", "doctor", "drph", "dnp", "doctoral"]):
        return "Doctoral"
    if any(term in lower for term in ["master", "mba", "ms", "mhs", "scm", "msph", "ma/", "mm"]):
        return "Master's"
    if "certificate" in lower:
        return "Certificate"
    if any(term in lower for term in ["bachelor", "minor"]):
        return "Undergraduate"
    return "Program"


def normalize_program_name(text):
    name = clean_text(text)
    trailing_terms = [
        "Master's", "Doctoral", "Undergraduate", "Certificate",
        "Full-time", "Part-time", "In-person", "Online", "Hybrid",
    ]
    for division in DIVISIONS:
        for term in trailing_terms:
            marker = f" {division} {term}"
            if marker in name:
                name = name.split(marker, 1)[0]
    for term in trailing_terms:
        doubled = f" {term} {term}"
        if doubled in name:
            name = name.split(doubled, 1)[0] + f" {term}"
    return clean_text(name)


def infer_division(name, href, context):
    search_area = clean_text(f"{context} {href} {name}").lower()
    for division in DIVISIONS:
        if division.lower() in search_area:
            return division
    if "engineering" in search_area or "computer" in search_area:
        return "Whiting School of Engineering"
    if "business" in search_area or "mba" in search_area:
        return "Carey Business School"
    if "public health" in search_area or "epidemiology" in search_area:
        return "Bloomberg School of Public Health"
    return "Johns Hopkins University"


def category_and_score(name, level, division):
    lower = name.lower()
    matched_categories = []
    matched_terms = []
    score = 50
    for category, terms in HIGH_DEMAND_KEYWORDS.items():
        hits = [term for term in terms if term in lower]
        if hits:
            matched_categories.append(category)
            matched_terms.extend(hits[:3])
            score += 12 + min(len(hits), 3) * 3

    if level in {"Master's", "Doctoral"}:
        score += 8
    if "/" in name or "dual degree" in lower:
        score += 6
        matched_terms.append("cross-disciplinary")
    if any(term in lower for term in ["artificial intelligence", "data science", "biostatistics", "public health", "biomedical engineering"]):
        score += 10
    if "certificate" in lower:
        score -= 4
    if "minor" in lower:
        score -= 8

    category = ", ".join(matched_categories) if matched_categories else "general_academic"
    reason = "; ".join(dict.fromkeys(matched_terms)) or f"Strong Johns Hopkins catalogue program in {division}."
    return min(score, 100), category, reason


def is_program_link(text, href):
    lower_text = text.lower()
    lower_href = href.lower()
    degree_terms = [
        "bachelor", "master", "minor", "certificate", "phd", "doctoral",
        "mba", "ms", "mhs", "scm", "msph", "dnp", "drph", "degree",
    ]
    ignored = [
        "catalogue home", "programs", "courses", "policies", "academic calendar",
        "admission", "tuition", "print options", "archive", "amendments",
    ]
    if lower_text in ignored:
        return False
    if len(text) < 5:
        return False
    if not any(term in lower_text for term in degree_terms):
        return False
    if "/course-descriptions/" in lower_href:
        return False
    if any(term in lower_href for term in ["policy", "calendar", "tuition", "admission"]):
        return False
    return True


def parse_programs(page_html, source_url, limit):
    parser = LinkParser()
    parser.feed(page_html)
    rows = []
    seen = set()
    for link in parser.links:
        name = normalize_program_name(link["text"])
        href = link["href"]
        if not is_program_link(name, href):
            continue
        full_url = urljoin(source_url, href)
        key = full_url.lower()
        if key in seen:
            continue
        seen.add(key)
        match_position = page_html.find(href)
        context = page_html[max(0, match_position - 2500):match_position] if match_position >= 0 else ""
        level = degree_level(name)
        division = infer_division(name, href, context)
        score, category, reason = category_and_score(name, level, division)
        rows.append({
            "rank": 0,
            "program_name": name,
            "degree_level": level,
            "division": division,
            "category": category,
            "ai_screening_score": score,
            "why_recommended": reason,
            "program_url": full_url,
            "source_url": source_url,
            "notes": "Parsed from the public Johns Hopkins University Academic Catalogue. Score is a workflow screening heuristic, not an official JHU ranking.",
        })

    rows.sort(key=lambda row: (-row["ai_screening_score"], row["program_name"]))
    for index, row in enumerate(rows[:limit], start=1):
        row["rank"] = index
    return rows[:limit]


def sample_rows():
    names = [
        ("Business Analytics and Artificial Intelligence, Master of Science", "Carey Business School"),
        ("Computer Science, Master of Science in Engineering", "Whiting School of Engineering"),
        ("Biostatistics, PhD", "Bloomberg School of Public Health"),
        ("Biomedical Engineering, Bachelor of Science", "Whiting School of Engineering"),
        ("Master of Public Health Program", "Bloomberg School of Public Health"),
    ]
    rows = []
    for name, division in names:
        level = degree_level(name)
        score, category, reason = category_and_score(name, level, division)
        rows.append({
            "rank": len(rows) + 1,
            "program_name": name,
            "degree_level": level,
            "division": division,
            "category": category,
            "ai_screening_score": score,
            "why_recommended": reason,
            "program_url": DEFAULT_SOURCE_URL,
            "source_url": DEFAULT_SOURCE_URL,
            "notes": "Sample fallback row for demo if the live catalogue cannot be parsed.",
        })
    return rows


def summarize(rows):
    top = rows[:5]
    names = "; ".join(f"{row['rank']}. {row['program_name']} ({row['division']})" for row in top)
    return (
        f"Found {len(rows)} candidate JHU programs. Top screening picks: {names}. "
        "These are selected by demand-area fit, graduate/professional depth, and cross-disciplinary signals."
    )


def main():
    payload = read_payload()
    source_url = payload.get("source_url") or DEFAULT_SOURCE_URL
    limit = max(1, min(int(payload.get("limit") or 40), 150))
    timeout = max(5, min(int(payload.get("timeout") or 20), 30))
    fallback_sample = bool(payload.get("fallback_sample", True))
    errors = []
    rows = []
    mode = "live"

    try:
        page_html = fetch_html(source_url, timeout)
        rows = parse_programs(page_html, source_url, limit)
    except Exception as exc:
        errors.append({"source": source_url, "error": str(exc)})

    if not rows and fallback_sample:
        rows = sample_rows()[:limit]
        mode = "sample_fallback"

    result = {
        "ok": bool(rows),
        "provider": "Johns Hopkins University Academic Catalogue",
        "source_url": source_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "row_count": len(rows),
        "summary": summarize(rows) if rows else "No programs parsed.",
        "rows": rows,
        "errors": errors,
        "email": {
            "subject": "Johns Hopkins program analysis workflow",
            "body": summarize(rows) if rows else "No Johns Hopkins programs were parsed from the catalogue page.",
        },
        "disclaimer": "Screening output is not an official Johns Hopkins ranking. Review program pages, admissions fit, prerequisites, cost, and career goals before deciding.",
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
