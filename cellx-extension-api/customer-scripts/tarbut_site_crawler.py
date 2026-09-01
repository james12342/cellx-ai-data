#!/usr/bin/env python3
import html
import json
import re
import sys
import time
from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen


DEFAULT_URL = "https://www.tarbut.com/"
ALLOWED_HOSTS = {"www.tarbut.com", "tarbut.com"}
SKIP_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".pdf",
    ".zip", ".mp4", ".mov", ".mp3", ".css", ".js", ".woff", ".woff2",
)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta = {}
        self.links = []
        self.headings = []
        self.text_parts = []
        self._tag_stack = []
        self._current_meta = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self._tag_stack.append(tag)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "meta":
            key = attrs.get("name") or attrs.get("property")
            content = attrs.get("content")
            if key and content:
                self.meta[key] = content

    def handle_endtag(self, tag):
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data):
        text = re.sub(r"\s+", " ", html.unescape(data or "")).strip()
        if not text:
            return
        tag = self._tag_stack[-1] if self._tag_stack else ""
        if tag == "title":
            self.title = f"{self.title} {text}".strip()
        if tag in {"h1", "h2", "h3"}:
            self.headings.append({"level": tag, "text": text})
        if tag not in {"script", "style", "noscript"}:
            self.text_parts.append(text)


def read_payload():
    raw = sys.stdin.read().strip() or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


def normalize_url(url, base=DEFAULT_URL):
    joined = urljoin(base, url)
    cleaned, _fragment = urldefrag(joined)
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc.lower() not in ALLOWED_HOSTS:
        return None
    if parsed.path.lower().endswith(SKIP_EXTENSIONS):
        return None
    path = parsed.path or "/"
    return parsed._replace(path=path, query=parsed.query).geturl()


def fetch(url, timeout):
    request = Request(
        url,
        headers={
            "User-Agent": "CellAIDataWorkflowDemo/1.0 (+https://app.cellaidata.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type:
            return "", content_type
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read(1200000).decode(charset, errors="replace")
        return body, content_type


def extract_contact(text):
    emails = sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)))
    phones = sorted(set(re.findall(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}", text)))
    return emails, phones


def page_to_row(url, parser, depth):
    all_text = re.sub(r"\s+", " ", " ".join(parser.text_parts)).strip()
    emails, phones = extract_contact(all_text)
    headings = " | ".join(item["text"] for item in parser.headings[:8])
    return {
        "url": url,
        "depth": depth,
        "title": parser.title,
        "description": parser.meta.get("description") or parser.meta.get("og:description") or "",
        "h1_h2_h3": headings,
        "emails": ", ".join(emails),
        "phones": ", ".join(phones),
        "text_summary": all_text[:1200],
        "word_count": len(all_text.split()),
        "internal_link_count": len(parser.links),
    }


def crawl(start_url, max_pages, max_depth, delay_seconds, timeout):
    start = normalize_url(start_url) or DEFAULT_URL
    queue = deque([(start, 0)])
    seen = set()
    rows = []
    errors = []

    while queue and len(rows) < max_pages:
        url, depth = queue.popleft()
        if url in seen or depth > max_depth:
            continue
        seen.add(url)
        try:
            body, content_type = fetch(url, timeout)
            if not body:
                continue
            parser = PageParser()
            parser.feed(body)
            rows.append(page_to_row(url, parser, depth))
            if depth < max_depth:
                for link in parser.links:
                    next_url = normalize_url(link, url)
                    if next_url and next_url not in seen:
                        queue.append((next_url, depth + 1))
            if delay_seconds:
                time.sleep(delay_seconds)
        except Exception as exc:
            errors.append({"url": url, "error": str(exc)})
    return rows, errors


def main():
    payload = read_payload()
    start_url = payload.get("start_url") or DEFAULT_URL
    max_pages = max(1, min(int(payload.get("max_pages") or 30), 80))
    max_depth = max(0, min(int(payload.get("max_depth") or 2), 4))
    delay_seconds = max(0.0, min(float(payload.get("delay_seconds") or 0.3), 2.0))
    timeout = max(3, min(int(payload.get("timeout") or 12), 25))
    rows, errors = crawl(start_url, max_pages, max_depth, delay_seconds, timeout)

    print(json.dumps({
        "ok": True,
        "source_url": start_url,
        "allowed_hosts": sorted(ALLOWED_HOSTS),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(rows),
        "error_count": len(errors),
        "rows": rows,
        "errors": errors[:20],
        "next_step": "Export rows to Excel or map fields into a CellX table.",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
