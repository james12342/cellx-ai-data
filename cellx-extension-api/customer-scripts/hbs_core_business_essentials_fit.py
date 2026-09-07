#!/usr/bin/env python3
import html
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_SOURCE_URL = "https://online.hbs.edu/courses/core-business-essentials"


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.meta = {}
        self.links = []
        self._active_href = None
        self._active_text = []
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            key = attrs.get("name") or attrs.get("property")
            content = attrs.get("content")
            if key and content:
                self.meta[key] = clean_text(content)
        if tag == "a" and attrs.get("href"):
            self._active_href = attrs.get("href")
            self._active_text = []

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._active_href:
            text = clean_text(" ".join(self._active_text))
            if text:
                self.links.append({"text": text, "href": self._active_href})
            self._active_href = None
            self._active_text = []

    def handle_data(self, data):
        text = clean_text(data)
        if not text:
            return
        if self._in_title:
            self.title = clean_text(f"{self.title} {text}")
        if self._active_href:
            self._active_text.append(text)
        self.text_parts.append(text)


def read_payload():
    raw = sys.stdin.read().strip() or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


def clean_text(value):
    value = html.unescape(str(value or ""))
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
        return response.read(2_500_000).decode(charset, errors="replace")


def fallback_course_facts(source_url):
    return {
        "course_name": "Core Business Essentials",
        "school": "Harvard Business School Online",
        "credential": "Credential of Core Business Essentials",
        "duration": "17 weeks",
        "time_commitment": "5-8 hours/week",
        "price_usd": 2799,
        "format": "Online, deadline-based, case-oriented learning",
        "courses": [
            "Business Analytics",
            "Business Strategy",
            "Financial Accounting",
            "Negotiation, Trust, and Ethics module",
            "Capstone project",
        ],
        "best_for": [
            "Students and founders who need business fluency",
            "People preparing for business school or entrepreneurship",
            "Builders who want stronger analytics, strategy, and accounting fundamentals",
        ],
        "source_url": source_url,
    }


def parse_course_page(page_html, source_url):
    parser = TextParser()
    parser.feed(page_html)
    text = clean_text(" ".join(parser.text_parts))[:12000]
    facts = fallback_course_facts(source_url)
    if parser.title:
        facts["page_title"] = parser.title
    description = parser.meta.get("description") or parser.meta.get("og:description")
    if description:
        facts["page_description"] = description

    price_match = re.search(r"\$ ?([0-9][0-9,]+)", text)
    if price_match:
        facts["price_usd"] = int(price_match.group(1).replace(",", ""))
    duration_match = re.search(r"(\d+\s*weeks?)", text, re.I)
    if duration_match:
        facts["duration"] = clean_text(duration_match.group(1))
    hours_match = re.search(r"(\d+\s*-\s*\d+\s*hrs?/week|\d+\s*-\s*\d+\s*hours?/week)", text, re.I)
    if hours_match:
        facts["time_commitment"] = clean_text(hours_match.group(1))

    course_terms = [
        "Business Analytics",
        "Business Strategy",
        "Financial Accounting",
        "Negotiation",
        "Trust",
        "Ethics",
        "Capstone",
    ]
    facts["detected_topics"] = [term for term in course_terms if term.lower() in text.lower()]
    facts["relevant_links"] = [
        {"text": link["text"], "url": urljoin(source_url, link["href"])}
        for link in parser.links[:8]
    ]
    return facts


def build_rows(facts):
    rows = [
        {
            "rank": 1,
            "factor": "Brand and signal",
            "evidence": f"{facts['school']} credential from {facts['course_name']}",
            "why_it_matters": "A recognizable business-school brand can strengthen a young founder's credibility when speaking with customers, mentors, and investors.",
            "fit_score": 95,
        },
        {
            "rank": 2,
            "factor": "Business fundamentals",
            "evidence": ", ".join(facts.get("courses", [])[:3]),
            "why_it_matters": "Analytics, strategy, and accounting directly support pricing, market sizing, financial planning, and investor storytelling.",
            "fit_score": 92,
        },
        {
            "rank": 3,
            "factor": "Founder project fit",
            "evidence": "Capstone project plus applied business cases",
            "why_it_matters": "The program can be connected to Cell AI Data by turning the startup itself into the project lens.",
            "fit_score": 90,
        },
        {
            "rank": 4,
            "factor": "Time and cost",
            "evidence": f"{facts.get('duration')} at about {facts.get('time_commitment')}; listed price about ${facts.get('price_usd')}",
            "why_it_matters": "The workload is meaningful, so it is strongest if scheduled around school, product demos, and competitions.",
            "fit_score": 78,
        },
    ]
    return rows


def main():
    payload = read_payload()
    source_url = clean_text(payload.get("source_url") or DEFAULT_SOURCE_URL)
    timeout = min(int(payload.get("timeout") or 20), 30)
    profile = clean_text(payload.get("student_profile") or "High-school founder building Cell AI Data, interested in entrepreneurship, AI workflows, and business strategy.")
    fallback_sample = bool(payload.get("fallback_sample", True))
    fetch_error = ""

    try:
        page_html = fetch_html(source_url, timeout)
        facts = parse_course_page(page_html, source_url)
    except Exception as error:
        if not fallback_sample:
            raise
        fetch_error = str(error)
        facts = fallback_course_facts(source_url)

    rows = build_rows(facts)
    email_body = (
        "Hi Harrison,\n\n"
        "Here is a quick HBS Online Core Business Essentials fit analysis.\n\n"
        f"Overall view: This looks like a strong fit for your current Cell AI Data work because it combines analytics, strategy, accounting, workplace dynamics, and a capstone project. "
        f"For a student founder, the strongest value is not only the Harvard/HBS signal, but the ability to explain product strategy, pricing, unit economics, and customer value more clearly.\n\n"
        "Top reasons:\n"
        "- Business Analytics can help you understand customer data, workflow ROI, and marketplace metrics.\n"
        "- Business Strategy can help you position Cell AI Data against workflow tools, AI agents, and low-code platforms.\n"
        "- Financial Accounting can improve investor conversations around revenue, costs, margins, and profitability.\n"
        "- The capstone can connect directly to your startup, making the coursework practical instead of abstract.\n\n"
        "Main caution: the program requires consistent weekly work, so it is best if you can protect time around school and product development.\n\n"
        f"Source: {source_url}\n"
    )
    sms = "HBS Online Core Business Essentials looks like a strong fit: brand signal + analytics + strategy + accounting for Cell AI Data. Main caution: 17-week workload."

    result = {
        "ok": True,
        "provider": "HBS Online",
        "source_url": source_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "fetch_error": fetch_error,
        "student_profile": profile,
        "course": facts,
        "row_count": len(rows),
        "rows": rows,
        "email": {
            "subject": "HBS Online Core Business Essentials fit analysis",
            "body": email_body,
        },
        "sms": sms,
        "message": "Built HBS course-fit rows, email body, and SMS summary.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
