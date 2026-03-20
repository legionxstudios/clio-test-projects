import unittest

from src.scrape_word_counts import PageAnalyzer, SitemapFetcher, WebpageCounter


class FakeClient:
    def __init__(self, payloads):
        self.payloads = payloads

    def get_text(self, url):
        value = self.payloads[url]
        return value.decode() if isinstance(value, bytes) else value

    def get_bytes(self, url):
        value = self.payloads[url]
        return value if isinstance(value, bytes) else value.encode()


class PageAnalyzerTests(unittest.TestCase):
    def test_excludes_navigation_and_footer_from_counts(self):
        html = """
        <html><body>
        <header><h1>Ignored heading</h1></header>
        <nav>pricing pricing pricing</nav>
        <main><h1>Pricing overview</h1><p>Pricing appears once here.</p></main>
        <footer>pricing again</footer>
        </body></html>
        """
        analyzer = PageAnalyzer()
        patterns = [{"name": "pricing", "mode": "exact", "regex": r"\bpricing\b", "case_sensitive": False}]
        result = analyzer.analyze_html("https://example.com", html, patterns)
        self.assertEqual(result.heading_counts["pricing"], 1)
        self.assertEqual(result.body_counts["pricing"], 2)

    def test_supports_regex_any_and_all_filters(self):
        html = "<body><main><h2>AI SEO Guide</h2><p>seo and ai improve organic visibility.</p></main></body>"
        analyzer = PageAnalyzer()
        patterns = [
            {"name": "regex", "mode": "regex", "value": r"ai|seo", "case_sensitive": False},
            {"name": "any", "mode": "any", "words": ["seo", "ppc"]},
            {"name": "all", "mode": "all", "words": ["ai", "visibility"]},
        ]
        result = analyzer.analyze_html("https://example.com", html, patterns)
        self.assertEqual(result.heading_counts["regex"], 2)
        self.assertEqual(result.body_counts["any"], 2)
        self.assertEqual(result.body_counts["all"], 1)


class SitemapFetcherTests(unittest.TestCase):
    def test_handles_sitemap_index(self):
        client = FakeClient(
            {
                "https://example.com/sitemap.xml": b"<sitemapindex><sitemap><loc>https://example.com/child.xml</loc></sitemap></sitemapindex>",
                "https://example.com/child.xml": b"<urlset><url><loc>https://example.com/a</loc></url><url><loc>https://example.com/b</loc></url></urlset>",
            }
        )
        urls = SitemapFetcher(client=client).fetch_urls("https://example.com/sitemap.xml")
        self.assertEqual(urls, ["https://example.com/a", "https://example.com/b"])


class WebpageCounterTests(unittest.TestCase):
    def test_builds_totals_and_page_results(self):
        client = FakeClient(
            {
                "https://example.com/sitemap.xml": b"<urlset><url><loc>https://example.com/page</loc></url></urlset>",
                "https://example.com/page": "<body><main><h1>Pricing</h1><p>Pricing page</p></main></body>",
            }
        )
        counter = WebpageCounter(client=client)
        patterns = [{"name": "pricing", "mode": "exact", "regex": r"\bpricing\b", "case_sensitive": False}]
        report = counter.run("https://example.com/sitemap.xml", patterns)
        self.assertEqual(report["totals"]["pricing"]["headings"], 1)
        self.assertEqual(report["totals"]["pricing"]["body"], 2)
        self.assertEqual(report["page_count"], 1)


if __name__ == "__main__":
    unittest.main()
