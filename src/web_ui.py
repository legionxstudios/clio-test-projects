#!/usr/bin/env python3
import html
import json
import os
import re
import traceback
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from src.scrape_word_counts import ScrapeError, WebpageCounter


def split_multiline(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def parse_csv_lines(value: str) -> list[str]:
    items = []
    for line in value.splitlines():
        line = line.strip()
        if line:
            items.append(line)
    return items


def build_patterns_from_form(form_data: dict[str, str]) -> list[dict]:
    patterns: list[dict] = []
    case_sensitive = form_data.get("case_sensitive") == "on"

    for item in split_multiline(form_data.get("words", "")):
        patterns.append({
            "name": item,
            "mode": "exact",
            "value": item,
            "regex": rf"\b{re.escape(item)}\b",
            "case_sensitive": case_sensitive,
        })

    for item in split_multiline(form_data.get("regexes", "")):
        patterns.append({
            "name": f"regex:{item}",
            "mode": "regex",
            "value": item,
            "case_sensitive": case_sensitive,
        })

    for item in parse_csv_lines(form_data.get("any_words", "")):
        words = [part.strip() for part in item.split(",") if part.strip()]
        patterns.append({"name": f"any:{'|'.join(words)}", "mode": "any", "words": words})

    for item in parse_csv_lines(form_data.get("all_words", "")):
        words = [part.strip() for part in item.split(",") if part.strip()]
        patterns.append({"name": f"all:{'&'.join(words)}", "mode": "all", "words": words})

    if not patterns:
        raise ScrapeError("Add at least one word, regex, OR filter, or AND filter before running the analysis.")

    return patterns


def html_page(body: str) -> bytes:
    page = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Sitemap Word Count UI</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ font-family: Arial, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }}
    .wrap {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 80px; }}
    .hero {{ margin-bottom: 24px; }}
    .hero h1 {{ margin: 0 0 10px; font-size: 2rem; }}
    .hero p {{ margin: 0; color: #cbd5e1; line-height: 1.5; }}
    .grid {{ display: grid; grid-template-columns: 420px 1fr; gap: 24px; align-items: start; }}
    .card {{ background: #111827; border: 1px solid #334155; border-radius: 16px; padding: 20px; box-shadow: 0 12px 30px rgba(0,0,0,.2); }}
    label {{ display: block; font-weight: bold; margin: 0 0 8px; }}
    input[type=text], input[type=number], textarea, select {{ width: 100%; box-sizing: border-box; border-radius: 10px; border: 1px solid #475569; background: #020617; color: #e2e8f0; padding: 10px 12px; margin-bottom: 16px; }}
    textarea {{ min-height: 88px; resize: vertical; }}
    .help {{ color: #94a3b8; font-size: .92rem; margin: -8px 0 16px; line-height: 1.4; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .checkbox {{ display: flex; gap: 8px; align-items: center; margin: 8px 0 20px; }}
    button {{ background: #38bdf8; color: #082f49; border: 0; border-radius: 999px; padding: 12px 18px; font-weight: bold; cursor: pointer; }}
    button:hover {{ background: #7dd3fc; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .95rem; }}
    th, td {{ border-bottom: 1px solid #334155; text-align: left; padding: 10px 8px; vertical-align: top; }}
    th {{ color: #7dd3fc; }}
    .error {{ border: 1px solid #ef4444; background: #450a0a; color: #fecaca; padding: 14px 16px; border-radius: 12px; margin-bottom: 20px; }}
    .muted {{ color: #94a3b8; }}
    pre {{ background: #020617; border: 1px solid #334155; border-radius: 12px; padding: 16px; overflow-x: auto; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} .row {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class=\"wrap\">{body}</div>
</body>
</html>"""
    return page.encode("utf-8")


def render_form(form_data: dict[str, str], result: dict | None = None, error: str | None = None) -> bytes:
    def value(name: str, default: str = "") -> str:
        return html.escape(form_data.get(name, default))

    checked = "checked" if form_data.get("case_sensitive") == "on" else ""
    table = render_results(result) if result else "<p class=\"muted\">Run an analysis to see totals and per-page counts here.</p>"
    error_block = f'<div class="error">{html.escape(error)}</div>' if error else ""
    body = f"""
    <section class=\"hero\">
      <h1>Sitemap Word Count UI</h1>
      <p>Analyze sitemap pages in your browser, separate heading counts from body counts, and ignore nav/footer chrome without using the CLI.</p>
    </section>
    {error_block}
    <div class=\"grid\">
      <form class=\"card\" method=\"post\" action=\"/analyze\">
        <label for=\"sitemap_url\">Sitemap URL</label>
        <input id=\"sitemap_url\" name=\"sitemap_url\" type=\"text\" value=\"{value('sitemap_url')}\" placeholder=\"https://example.com/sitemap.xml\" required>

        <div class=\"row\">
          <div>
            <label for=\"limit\">Page limit</label>
            <input id=\"limit\" name=\"limit\" type=\"number\" min=\"1\" value=\"{value('limit')}\" placeholder=\"25\">
          </div>
          <div>
            <label for=\"output\">Output mode</label>
            <select id=\"output\" name=\"output\">
              <option value=\"table\">Table</option>
              <option value=\"json\" {'selected' if form_data.get('output') == 'json' else ''}>JSON</option>
            </select>
          </div>
        </div>

        <label for=\"words\">Exact words / phrases</label>
        <textarea id=\"words\" name=\"words\" placeholder=\"pricing\ncontent marketing\">{value('words')}</textarea>
        <div class=\"help\">One exact term or phrase per line.</div>

        <label for=\"regexes\">Regex filters</label>
        <textarea id=\"regexes\" name=\"regexes\" placeholder=\"seo|search engine optimization\nai|artificial intelligence\">{value('regexes')}</textarea>
        <div class=\"help\">One regex per line for alternate spellings or patterns.</div>

        <label for=\"any_words\">OR filters</label>
        <textarea id=\"any_words\" name=\"any_words\" placeholder=\"seo,ppc,analytics\nfaq,knowledge base,support\">{value('any_words')}</textarea>
        <div class=\"help\">One comma-separated group per line. Counts any matching token in each group.</div>

        <label for=\"all_words\">AND filters</label>
        <textarea id=\"all_words\" name=\"all_words\" placeholder=\"seo,visibility\nai,automation\">{value('all_words')}</textarea>
        <div class=\"help\">One comma-separated group per line. Returns 1 when all words in the group appear in a section.</div>

        <label for=\"exclude_classes\">Extra excluded classes</label>
        <textarea id=\"exclude_classes\" name=\"exclude_classes\" placeholder=\"sidebar\nbreadcrumb\nnewsletter-signup\">{value('exclude_classes')}</textarea>
        <div class=\"help\">Optional. One CSS class name per line, without or with a leading dot.</div>

        <label class=\"checkbox\"><input type=\"checkbox\" name=\"case_sensitive\" {checked}> Case-sensitive exact + regex matching</label>
        <button type=\"submit\">Run analysis</button>
      </form>
      <section class=\"card\">{table}</section>
    </div>
    """
    return html_page(body)


def render_results(result: dict) -> str:
    totals_rows = []
    for name, counts in result.get("totals", {}).items():
        totals_rows.append(
            f"<tr><td>{html.escape(name)}</td><td>{counts['headings']}</td><td>{counts['body']}</td></tr>"
        )
    page_rows = []
    for page in result.get("pages", []):
        detail_bits = []
        for pattern_name, heading_count in page.get("headings", {}).items():
            body_count = page.get("body", {}).get(pattern_name, 0)
            detail_bits.append(f"<div><strong>{html.escape(pattern_name)}</strong>: headings={heading_count}, body={body_count}</div>")
        page_rows.append(f"<tr><td>{html.escape(page['url'])}</td><td>{''.join(detail_bits)}</td></tr>")
    return f"""
      <h2>Results</h2>
      <p class=\"muted\">Pages analyzed: {result.get('page_count', 0)}</p>
      <h3>Totals</h3>
      <table>
        <thead><tr><th>Pattern</th><th>Headings</th><th>Body</th></tr></thead>
        <tbody>{''.join(totals_rows) or '<tr><td colspan="3">No totals available.</td></tr>'}</tbody>
      </table>
      <h3>Per-page counts</h3>
      <table>
        <thead><tr><th>URL</th><th>Counts</th></tr></thead>
        <tbody>{''.join(page_rows) or '<tr><td colspan="2">No pages analyzed.</td></tr>'}</tbody>
      </table>
      <h3>Raw JSON</h3>
      <pre>{html.escape(json.dumps(result, indent=2))}</pre>
    """


def parse_post_body(environ) -> dict[str, str]:
    content_length = int(environ.get("CONTENT_LENGTH") or 0)
    body = environ["wsgi.input"].read(content_length) if content_length else b""
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items()}


def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")

    if method == "GET" and path == "/":
        response = render_form({"output": "table"})
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(response)))])
        return [response]

    if method == "POST" and path == "/analyze":
        form_data = parse_post_body(environ)
        form_data.setdefault("output", "table")
        try:
            patterns = build_patterns_from_form(form_data)
            counter = WebpageCounter()
            exclude_classes = [item.lstrip('.') for item in split_multiline(form_data.get("exclude_classes", ""))]
            counter.analyzer.extra_exclude_classes.extend(exclude_classes)
            limit_raw = form_data.get("limit", "").strip()
            limit = int(limit_raw) if limit_raw else None
            result = counter.run(form_data["sitemap_url"].strip(), patterns, limit=limit)
            response = render_form(form_data, result=result)
            start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(response)))])
            return [response]
        except Exception as exc:
            response = render_form(form_data, error=f"{exc}\n\n{traceback.format_exc(limit=2)}")
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(response)))])
            return [response]

    response = html_page("<div class='card'><h1>Not found</h1><p class='muted'>Try the homepage.</p></div>")
    start_response("404 Not Found", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(response)))])
    return [response]


def main():
    port = int(os.environ.get("PORT", "7860"))
    with make_server("0.0.0.0", port, app) as server:
        print(f"Serving Sitemap Word Count UI on http://0.0.0.0:{port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
