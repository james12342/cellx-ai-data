#!/usr/bin/env python3
import html
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_SOURCE_URL = "https://www.duke.edu/"


class DukePageParser(HTMLParser):
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


def fallback_duke_facts(source_url):
    return {
        "school_name": "Duke University",
        "location": "Durham, North Carolina",
        "positioning": "Research university with strong academics, interdisciplinary research, entrepreneurship, health, engineering, public policy, business, arts, and campus culture.",
        "strength_areas": [
            "Pratt School of Engineering",
            "Fuqua School of Business",
            "Duke Research & Innovation",
            "Innovation & Entrepreneurship",
            "Rhodes Information Initiative for data and big-data work",
            "Global Health Institute",
            "Sanford School of Public Policy",
            "Strong campus life and athletics",
        ],
        "best_for": [
            "Students who want rigorous academics plus collaborative campus life",
            "Students interested in AI, data, engineering, business, health, policy, or entrepreneurship",
            "Student founders who want research access, mentors, alumni, and practical innovation programs",
        ],
        "source_url": source_url,
    }


def parse_duke_page(page_html, source_url):
    parser = DukePageParser()
    parser.feed(page_html)
    text = clean_text(" ".join(parser.text_parts))[:16000]
    facts = fallback_duke_facts(source_url)
    if parser.title:
        facts["page_title"] = parser.title
    description = parser.meta.get("description") or parser.meta.get("og:description")
    if description:
        facts["page_description"] = description

    keywords = [
        "Academics",
        "Research",
        "Admissions",
        "Duke Research & Innovation",
        "Innovation & Entrepreneurship",
        "Pratt School of Engineering",
        "Fuqua School of Business",
        "Rhodes Information Initiative",
        "Global Health Institute",
        "Interdisciplinary Programs",
        "Duke Arts",
        "Athletics",
        "Undergraduate Research",
    ]
    facts["detected_signals"] = [keyword for keyword in keywords if keyword.lower() in text.lower()]
    selected_links = []
    keep_terms = [
        "academics", "research", "admissions", "engineering", "business",
        "innovation", "entrepreneurship", "bigdata", "undergraduate research",
        "campus life", "financial aid", "fuqua", "pratt",
    ]
    for link in parser.links:
        combined = f"{link['text']} {link['href']}".lower()
        if any(term in combined for term in keep_terms):
            selected_links.append({"text": link["text"], "url": urljoin(source_url, link["href"])})
        if len(selected_links) >= 12:
            break
    facts["relevant_links"] = selected_links
    return facts


def build_rows(facts):
    return [
        {
            "rank": 1,
            "factor": "Academic range",
            "evidence": "Duke links academics, research, engineering, business, public policy, health, arts, and interdisciplinary programs.",
            "why_it_matters": "A founder working on AI workflow software needs technical depth, business thinking, and real-world problem framing.",
            "fit_score": 96,
        },
        {
            "rank": 2,
            "factor": "Research and innovation ecosystem",
            "evidence": "Duke Research & Innovation, Innovation & Entrepreneurship, undergraduate research, and data-focused initiatives are visible in official Duke links.",
            "why_it_matters": "This can help turn Cell AI Data from a demo into research-backed products, experiments, and startup opportunities.",
            "fit_score": 94,
        },
        {
            "rank": 3,
            "factor": "AI, data, and engineering fit",
            "evidence": "Pratt Engineering and Rhodes Information Initiative align with AI, analytics, software, and data projects.",
            "why_it_matters": "The environment fits a student who wants to build workflow agents, data products, and automation platforms.",
            "fit_score": 92,
        },
        {
            "rank": 4,
            "factor": "Business and entrepreneurship fit",
            "evidence": "Fuqua School of Business and Duke Innovation & Entrepreneurship create a bridge between product, customers, pricing, and venture building.",
            "why_it_matters": "It can help you explain market strategy, revenue model, operations, and investor story more clearly.",
            "fit_score": 91,
        },
        {
            "rank": 5,
            "factor": "Campus community",
            "evidence": "Duke emphasizes shared spaces, campus life, arts, athletics, and a strong student community.",
            "why_it_matters": "For a high-school founder, a collaborative peer network can be as valuable as classes.",
            "fit_score": 88,
        },
        {
            "rank": 6,
            "factor": "Main caution",
            "evidence": "Duke is highly selective and academically demanding.",
            "why_it_matters": "The best application story should connect your AI workflow project, customer demos, market insight, and learning goals.",
            "fit_score": 80,
        },
    ]


def main():
    payload = read_payload()
    source_url = clean_text(payload.get("source_url") or DEFAULT_SOURCE_URL)
    timeout = min(int(payload.get("timeout") or 20), 30)
    profile = clean_text(payload.get("student_profile") or "High-school founder building Cell AI Data, interested in AI workflow automation, entrepreneurship, data, and business strategy.")
    fallback_sample = bool(payload.get("fallback_sample", True))
    fetch_error = ""

    try:
        page_html = fetch_html(source_url, timeout)
        facts = parse_duke_page(page_html, source_url)
    except Exception as error:
        if not fallback_sample:
            raise
        fetch_error = str(error)
        facts = fallback_duke_facts(source_url)

    rows = build_rows(facts)
    email_body = (
        "Hi Harrison,\n\n"
        "Here is a quick Duke University fit analysis based on Duke's public website signals.\n\n"
        "Overall view: Duke looks like a strong fit because it combines rigorous academics, research, engineering, business, entrepreneurship, data science, and a lively campus community. "
        "For your Cell AI Data work, the strongest match is the mix of Pratt Engineering, Fuqua-style business thinking, Duke Research & Innovation, Innovation & Entrepreneurship, and data-focused initiatives.\n\n"
        "Why Duke fits you:\n"
        "- It supports interdisciplinary builders, which matches an AI workflow platform that crosses software, business operations, data, and automation.\n"
        "- Duke's research and innovation ecosystem can help you turn demos into stronger products and experiments.\n"
        "- Engineering and data resources align with workflow agents, data pipelines, and AI-powered decision systems.\n"
        "- Business and entrepreneurship resources can help with pricing, go-to-market, marketplace strategy, and investor communication.\n"
        "- Duke's campus culture gives you a strong peer network and high-energy environment.\n\n"
        "Main caution: Duke is very selective and demanding, so your strongest story should show real initiative: product demos, customer problems, workflow examples, and measurable impact.\n\n"
        f"Source: {source_url}\n"
    )
    sms = "Duke looks like a strong fit for Harrison: engineering + data + business + entrepreneurship + research culture. Best angle: connect Cell AI Data demos to real-world impact."

    result = {
        "ok": True,
        "provider": "Duke University",
        "source_url": source_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "fetch_error": fetch_error,
        "student_profile": profile,
        "school": facts,
        "row_count": len(rows),
        "rows": rows,
        "email": {
            "subject": "Duke University fit analysis",
            "body": email_body,
        },
        "sms": sms,
        "message": "Built Duke attendance-fit rows, email body, and SMS summary.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
