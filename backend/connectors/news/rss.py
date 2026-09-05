from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree


class RssItem:
    def __init__(self, title: str, link: str, published_at: str | None, source: str, snippet: str):
        self.title = title
        self.link = link
        self.published_at = published_at
        self.source = source
        self.snippet = snippet


def decode_xml(value: str) -> str:
    out = value
    for _ in range(3):
        out = re.sub(r"<!\[CDATA\[([\s\S]*?)\]\]>", r"\1", out)
        out = html.unescape(out)
    return out.strip()


def strip_html(value: str) -> str:
    value = decode_xml(value)
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.I)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def child_text(item: ElementTree.Element, names: set[str]) -> str:
    for child in item.iter():
        name = child.tag.rsplit("}", 1)[-1].lower()
        if name in names and child.text:
            return child.text
    return ""


def unwrap_bing(url: str) -> str:
    try:
        real = parse_qs(urlparse(url).query).get("url", [None])[0]
        return real or url
    except ValueError:
        return url


def source_from_title(title: str) -> tuple[str, str]:
    cut = title.rfind(" - ")
    if 12 < cut < len(title) - 2:
        return title[:cut].strip(), title[cut + 3 :].strip()
    return title, ""


def clean_snippet(raw: str, title: str) -> str:
    snippet = strip_html(raw)[:280]
    if not snippet or snippet.startswith("http") or "href=" in snippet:
        return ""
    if title and snippet.lower().startswith(title.lower()[:40]):
        return ""
    return snippet


def parse_date(value: str) -> str | None:
    if not value:
        return None
    try:
        from email.utils import parsedate_to_datetime
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, IndexError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            return None


def parse_rss(xml: str) -> list[RssItem]:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return []

    items: list[RssItem] = []
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1].lower() != "item":
            continue
        raw_title = strip_html(child_text(item, {"title"}))
        if not raw_title:
            continue
        title, title_source = source_from_title(raw_title)
        link = strip_html(child_text(item, {"link", "guid"}))
        link = unwrap_bing(link)
        pub = strip_html(child_text(item, {"pubdate", "published", "date"}))
        source = strip_html(child_text(item, {"source", "creator"})) or title_source or "News"
        description = child_text(item, {"description", "summary"})
        items.append(RssItem(title, link, parse_date(pub), source, clean_snippet(description, title)))
    return items


def origin_host(url: str) -> str:
    try:
        return urlparse(url).hostname.removeprefix("www.") if urlparse(url).hostname else ""
    except ValueError:
        return ""
