#!/usr/bin/env python3
import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


DEFAULT_URL = "https://playvalorant.com/en-us/agents/"
ALLOWED_HOST = "playvalorant.com"


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta = {}
        self.links = []
        self.parts = []
        self._stack = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self._stack.append(tag)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "meta":
            key = attrs.get("name") or attrs.get("property")
            content = attrs.get("content")
            if key and content:
                self.meta[key] = content

    def handle_endtag(self, tag):
        if self._stack:
            self._stack.pop()

    def handle_data(self, data):
        text = re.sub(r"\s+", " ", html.unescape(data or "")).strip()
        if not text:
            return
        tag = self._stack[-1] if self._stack else ""
        if tag == "title":
            self.title = f"{self.title} {text}".strip()
        if tag not in {"script", "style", "noscript"}:
            self.parts.append(text)


def read_payload():
    raw = sys.stdin.read().strip() or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


def fetch(url, timeout=15):
    request = Request(
        url,
        headers={
            "User-Agent": "CellAIDataWorkflowDemo/1.0 (+https://app.cellaidata.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read(1800000).decode(charset, errors="replace")


def normalize_agent_url(href, base):
    url = urljoin(base, href)
    parsed = urlparse(url)
    if parsed.netloc.lower() != ALLOWED_HOST:
        return None
    match = re.match(r"^/en-us/agents/([^/?#]+)/?$", parsed.path)
    if not match:
        return None
    slug = match.group(1).strip().lower()
    if not slug:
        return None
    return f"https://{ALLOWED_HOST}/en-us/agents/{slug}/"


def agent_links(index_html, index_url):
    parser = TextParser()
    parser.feed(index_html)
    urls = []
    seen = set()
    for link in parser.links:
        url = normalize_agent_url(link, index_url)
        if url and url not in seen:
            urls.append(url)
            seen.add(url)
    return urls


def next_data(html_text):
    marker = '<script id="__NEXT_DATA__" type="application/json">'
    start = html_text.find(marker)
    if start < 0:
        return None
    start += len(marker)
    end = html_text.find("</script>", start)
    if end < 0:
        return None
    try:
        return json.loads(html_text[start:end])
    except Exception:
        return None


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def clean_text(value):
    if value is None:
        return ""
    if isinstance(value, dict):
        value = value.get("body") or value.get("text") or value.get("title") or value.get("name") or ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def media_url(media):
    if not isinstance(media, dict):
        return ""
    if media.get("url"):
        return media.get("url")
    sources = media.get("sources")
    if isinstance(sources, list) and sources:
        return sources[0].get("src", "") if isinstance(sources[0], dict) else ""
    return ""


def parse_structured_agent(data):
    page = ((data or {}).get("props") or {}).get("pageProps", {}).get("page", {})
    blades = page.get("blades") if isinstance(page, dict) else []
    if not isinstance(blades, list):
        return {}

    masthead = next((blade for blade in blades if isinstance(blade, dict) and blade.get("type") == "characterMasthead"), {})
    ability_blade = next((blade for blade in blades if isinstance(blade, dict) and blade.get("type") == "iconTab"), {})
    role_items = ((masthead.get("role") or {}).get("roles") or []) if isinstance(masthead.get("role"), dict) else []
    role = ", ".join(clean_text(item.get("name")) for item in role_items if isinstance(item, dict))

    abilities = []
    for index, group in enumerate(ability_blade.get("groups") or [], start=1):
        if not isinstance(group, dict):
            continue
        content = group.get("content") or {}
        ability = {
            "slot": index,
            "name": clean_text(content.get("title")),
            "description": clean_text(content.get("description")),
            "icon_url": media_url(group.get("thumbnail")),
            "video_url": media_url(content.get("media")),
        }
        if ability["name"] or ability["description"]:
            abilities.append(ability)

    return {
        "agent": clean_text(masthead.get("title")),
        "role": role,
        "bio": clean_text(masthead.get("description")),
        "background_url": media_url((masthead.get("backdrop") or {}).get("background")) if isinstance(masthead.get("backdrop"), dict) else "",
        "abilities": abilities,
    }


def find_agent_data(data):
    if not data:
        return {}
    candidates = []
    for item in walk(data):
        keys = {str(key).lower() for key in item.keys()}
        score = 0
        if {"name", "description"} <= keys:
            score += 2
        if "role" in keys or "roleuuid" in keys:
            score += 2
        if "abilities" in keys or "ability" in keys:
            score += 3
        if "displayname" in keys:
            score += 2
        if score:
            candidates.append((score, item))
    return sorted(candidates, key=lambda pair: pair[0], reverse=True)[0][1] if candidates else {}


def extract_ability_objects(data):
    abilities = []
    for item in walk(data):
        for key, value in item.items():
            if str(key).lower() in {"abilities", "abilitylist", "specialabilities"} and isinstance(value, list):
                for ability in value:
                    if isinstance(ability, dict):
                        name = clean_text(ability.get("name") or ability.get("displayName") or ability.get("title"))
                        description = clean_text(ability.get("description") or ability.get("body") or ability.get("text"))
                        if name or description:
                            abilities.append({"name": name, "description": description})
    deduped = []
    seen = set()
    for ability in abilities:
        key = (ability.get("name"), ability.get("description"))
        if key not in seen:
            deduped.append(ability)
            seen.add(key)
    return deduped[:8]


def parse_from_text(page_html, url):
    parser = TextParser()
    parser.feed(page_html)
    parts = [part for part in parser.parts if part]
    title = parser.title or parts[0] if parts else ""
    name = clean_text(title.split("|")[0])
    joined = " ".join(parts)
    role = ""
    role_match = re.search(r"\bROLE\s+([A-Za-z /-]+?)\s+SPECIAL ABILITIES\b", joined, re.I)
    if role_match:
        role = clean_text(role_match.group(1))
    bio = ""
    if name and name in parts:
        index = parts.index(name)
        for item in parts[index + 1:index + 8]:
            if item.upper() == "ROLE":
                break
            if len(item.split()) > 8:
                bio = item
                break
    ability_text = joined.split("SPECIAL ABILITIES", 1)[-1] if "SPECIAL ABILITIES" in joined else ""
    ability_names = re.findall(r"\b([A-Z][A-Z/' -]{2,})\b", ability_text)
    abilities = []
    for ability_name in ability_names[:4]:
        marker = ability_name
        pos = ability_text.find(marker)
        description = clean_text(ability_text[pos + len(marker):pos + len(marker) + 550])
        abilities.append({"name": clean_text(marker), "description": description})
    return {
        "agent": name,
        "role": role,
        "bio": bio,
        "abilities": abilities,
        "page_title": parser.title,
        "url": url,
    }


def parse_agent_page(url, timeout):
    page_html = fetch(url, timeout)
    data = next_data(page_html)
    structured = parse_structured_agent(data)
    item = find_agent_data(data)
    fallback = parse_from_text(page_html, url)
    name = structured.get("agent") or clean_text(item.get("name") or item.get("displayName") or item.get("title")) or fallback["agent"]
    role_value = item.get("role")
    if isinstance(role_value, dict):
        role = clean_text(role_value.get("name") or role_value.get("displayName") or role_value.get("title"))
    else:
        role = clean_text(role_value) or fallback["role"]
    role = structured.get("role") or role
    bio = structured.get("bio") or clean_text(item.get("description") or item.get("bio") or item.get("body")) or fallback["bio"]
    abilities = structured.get("abilities") or extract_ability_objects(data) or fallback["abilities"]
    row = {
        "agent": name,
        "slug": urlparse(url).path.strip("/").split("/")[-1],
        "role": role,
        "bio": bio,
        "ability_count": len(abilities),
        "abilities": abilities,
        "ability_names": ", ".join(ability.get("name", "") for ability in abilities if ability.get("name")),
        "background_url": structured.get("background_url", ""),
        "page_title": fallback["page_title"],
        "url": url,
    }
    for index, ability in enumerate(abilities[:4], start=1):
        row[f"ability_{index}_name"] = ability.get("name", "")
        row[f"ability_{index}_description"] = ability.get("description", "")
        row[f"ability_{index}_icon_url"] = ability.get("icon_url", "")
        row[f"ability_{index}_video_url"] = ability.get("video_url", "")
    return row


def main():
    payload = read_payload()
    index_url = payload.get("url") or DEFAULT_URL
    max_agents = max(1, min(int(payload.get("max_agents") or 40), 60))
    delay_seconds = max(0.0, min(float(payload.get("delay_seconds") or 0.2), 2.0))
    timeout = max(5, min(int(payload.get("timeout") or 15), 30))
    index_html = fetch(index_url, timeout)
    urls = agent_links(index_html, index_url)[:max_agents]
    rows = []
    errors = []
    for url in urls:
        try:
            rows.append(parse_agent_page(url, timeout))
            if delay_seconds:
                time.sleep(delay_seconds)
        except Exception as exc:
            errors.append({"url": url, "error": str(exc)})

    print(json.dumps({
        "ok": True,
        "source_url": index_url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(rows),
        "error_count": len(errors),
        "rows": rows,
        "errors": errors,
        "next_step": "Export rows to Excel or map agent fields into a CellX table.",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
