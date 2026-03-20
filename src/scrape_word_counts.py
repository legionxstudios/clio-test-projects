#!/usr/bin/env python3
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import List, Sequence
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree

DEFAULT_EXCLUDE_TAGS = {"nav", "header", "footer"}
DEFAULT_EXCLUDE_CLASSES = {"nav", "navbar", "menu", "footer", "site-footer", "site-header"}
DEFAULT_EXCLUDE_ROLES = {"navigation"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


@dataclass
class PageMatchResult:
    url: str
    heading_counts: Counter
    body_counts: Counter


class ScrapeError(RuntimeError):
    pass


class HTMLSectionParser(HTMLParser):
    def __init__(self, extra_exclude_classes: Sequence[str] | None = None):
        super().__init__()
        self.heading_parts: List[str] = []
        self.body_parts: List[str] = []
        self.skip_stack: List[bool] = []
        self.in_heading = 0
        self.extra_exclude_classes = {item.lstrip('.') for item in (extra_exclude_classes or [])}

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = set((attrs_dict.get("class") or "").split())
        role = (attrs_dict.get("role") or "").strip().lower()
        parent_skipped = any(self.skip_stack)
        should_skip = parent_skipped or self._should_exclude(tag, classes, role)
        self.skip_stack.append(should_skip)
        if not should_skip and tag.lower() in HEADING_TAGS:
            self.in_heading += 1

    def handle_endtag(self, tag):
        if self.skip_stack:
            was_skipped = self.skip_stack.pop()
        else:
            was_skipped = False
        if not was_skipped and tag.lower() in HEADING_TAGS and self.in_heading > 0:
            self.in_heading -= 1

    def handle_data(self, data):
        if any(self.skip_stack):
            return
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        self.body_parts.append(cleaned)
        if self.in_heading > 0:
            self.heading_parts.append(cleaned)

    def _should_exclude(self, tag: str, classes: set[str], role: str) -> bool:
        lowered_tag = tag.lower()
        return (
            lowered_tag in DEFAULT_EXCLUDE_TAGS
            or role in DEFAULT_EXCLUDE_ROLES
            or bool(classes & DEFAULT_EXCLUDE_CLASSES)
            or bool(classes & self.extra_exclude_classes)
        )


class HttpClient:
    def __init__(self, timeout: int = 20, user_agent: str = "sitemap-word-count-scraper/1.0"):
        self.timeout = timeout
        self.user_agent = user_agent

    def get_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": self.user_agent})
        with urlopen(request, timeout=self.timeout) as response:
            return response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")

    def get_bytes(self, url: str) -> bytes:
        request = Request(url, headers={"User-Agent": self.user_agent})
        with urlopen(request, timeout=self.timeout) as response:
            return response.read()


class PageAnalyzer:
    def __init__(self, extra_exclude_classes: Sequence[str] | None = None):
        self.extra_exclude_classes = list(extra_exclude_classes or [])

    def analyze_html(self, url: str, html: str, patterns: Sequence[dict]) -> PageMatchResult:
        parser = HTMLSectionParser(extra_exclude_classes=self.extra_exclude_classes)
        parser.feed(html)
        heading_text = "\n".join(parser.heading_parts)
        body_text = "\n".join(parser.body_parts)

        heading_counts = Counter()
        body_counts = Counter()
        for pattern in patterns:
            heading_counts[pattern["name"]] = self._count_matches(heading_text, pattern)
            body_counts[pattern["name"]] = self._count_matches(body_text, pattern)

        return PageMatchResult(url=url, heading_counts=heading_counts, body_counts=body_counts)

    @staticmethod
    def _count_matches(text: str, pattern: dict) -> int:
        mode = pattern["mode"]
        if mode == "exact":
            flags = 0 if pattern.get("case_sensitive") else re.IGNORECASE
            return len(re.findall(pattern["regex"], text, flags=flags))
        if mode == "regex":
            flags = 0 if pattern.get("case_sensitive") else re.IGNORECASE
            return len(re.findall(pattern["value"], text, flags=flags))
        tokens = re.findall(r"\b[\w'-]+\b", text.lower())
        words = [word.lower() for word in pattern["words"]]
        if mode == "any":
            return sum(token in words for token in tokens)
        if mode == "all":
            joined_text = text.lower()
            return int(all(word in joined_text for word in words))
        raise ScrapeError(f"Unsupported pattern mode: {mode}")


class SitemapFetcher:
    def __init__(self, client: HttpClient | None = None):
        self.client = client or HttpClient()

    def fetch_urls(self, sitemap_url: str) -> List[str]:
        xml_root = ElementTree.fromstring(self.client.get_bytes(sitemap_url))
        tag_name = self._strip_namespace(xml_root.tag)
        if tag_name == "urlset":
            return self._extract_urlset(xml_root)
        if tag_name == "sitemapindex":
            return self._extract_sitemap_index(xml_root, sitemap_url)
        raise ScrapeError(f"Unsupported sitemap root tag: {xml_root.tag}")

    def _extract_urlset(self, root: ElementTree.Element) -> List[str]:
        urls = []
        for url_node in root.findall(".//{*}url"):
            loc = url_node.find("{*}loc")
            if loc is not None and loc.text:
                urls.append(loc.text.strip())
        return urls

    def _extract_sitemap_index(self, root: ElementTree.Element, sitemap_url: str) -> List[str]:
        urls: List[str] = []
        for sitemap_node in root.findall(".//{*}sitemap"):
            loc = sitemap_node.find("{*}loc")
            if loc is None or not loc.text:
                continue
            urls.extend(self.fetch_urls(urljoin(sitemap_url, loc.text.strip())))
        return urls

    @staticmethod
    def _strip_namespace(tag: str) -> str:
        return tag.split("}", 1)[-1]


class WebpageCounter:
    def __init__(self, client: HttpClient | None = None):
        self.client = client or HttpClient()
        self.analyzer = PageAnalyzer()
        self.sitemaps = SitemapFetcher(client=self.client)

    def run(self, sitemap_url: str, patterns: Sequence[dict], limit: int | None = None) -> dict:
        urls = self.sitemaps.fetch_urls(sitemap_url)
        if limit is not None:
            urls = urls[:limit]
        results = []
        totals = defaultdict(lambda: {"headings": 0, "body": 0})
        for url in urls:
            page_result = self.analyzer.analyze_html(url, self.client.get_text(url), patterns)
            results.append({"url": url, "headings": dict(page_result.heading_counts), "body": dict(page_result.body_counts)})
            for pattern in patterns:
                name = pattern["name"]
                totals[name]["headings"] += page_result.heading_counts[name]
                totals[name]["body"] += page_result.body_counts[name]
        return {"sitemap_url": sitemap_url, "page_count": len(results), "patterns": patterns, "totals": dict(totals), "pages": results}


def build_patterns(args: argparse.Namespace) -> List[dict]:
    patterns: List[dict] = []
    for item in args.word:
        patterns.append({"name": item, "mode": "exact", "value": item, "regex": rf"\b{re.escape(item)}\b", "case_sensitive": args.case_sensitive})
    for item in args.regex:
        patterns.append({"name": f"regex:{item}", "mode": "regex", "value": item, "case_sensitive": args.case_sensitive})
    for item in args.any_words:
        words = [part.strip() for part in item.split(",") if part.strip()]
        patterns.append({"name": f"any:{'|'.join(words)}", "mode": "any", "words": words})
    for item in args.all_words:
        words = [part.strip() for part in item.split(",") if part.strip()]
        patterns.append({"name": f"all:{'&'.join(words)}", "mode": "all", "words": words})
    if not patterns:
        raise ScrapeError("At least one filter is required. Use --word, --regex, --any-words, or --all-words.")
    return patterns


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape pages from a sitemap and count keyword usage in headings and body text.")
    parser.add_argument("sitemap_url", help="XML sitemap URL to crawl")
    parser.add_argument("--word", action="append", default=[], help="Exact word or phrase to count")
    parser.add_argument("--regex", action="append", default=[], help="Regex pattern to count")
    parser.add_argument("--any-words", action="append", default=[], help="Comma-separated list; counts any token matching any listed word")
    parser.add_argument("--all-words", action="append", default=[], help="Comma-separated list; counts 1 when all listed words appear on a page section")
    parser.add_argument("--limit", type=int, help="Only analyze the first N sitemap URLs")
    parser.add_argument("--case-sensitive", action="store_true", help="Make exact and regex filters case-sensitive")
    parser.add_argument("--exclude-class", action="append", default=[], help="Additional CSS class names to exclude from counting")
    parser.add_argument("--output", choices=["json", "table"], default="json", help="Output format")
    return parser.parse_args(argv)


def render_table(report: dict) -> str:
    lines = [f"Sitemap: {report['sitemap_url']}", f"Pages analyzed: {report['page_count']}", "", "Totals:"]
    for name, counts in report["totals"].items():
        lines.append(f"- {name}: headings={counts['headings']}, body={counts['body']}")
    lines.append("")
    lines.append("Per-page results:")
    for page in report["pages"]:
        lines.append(f"- {page['url']}")
        for name, heading_count in page["headings"].items():
            lines.append(f"  * {name}: headings={heading_count}, body={page['body'][name]}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        patterns = build_patterns(args)
        counter = WebpageCounter()
        if args.exclude_class:
            counter.analyzer.extra_exclude_classes.extend([item.lstrip('.') for item in args.exclude_class])
        report = counter.run(args.sitemap_url, patterns, limit=args.limit)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2) if args.output == "json" else render_table(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
