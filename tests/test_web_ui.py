import unittest
from unittest.mock import patch

from src.web_ui import app, build_patterns_from_form


class WebUiUnitTests(unittest.TestCase):
    def test_build_patterns_from_form_supports_all_modes(self):
        patterns = build_patterns_from_form(
            {
                "words": "pricing\ncontent marketing",
                "regexes": "seo|search engine optimization",
                "any_words": "ai,automation",
                "all_words": "seo,visibility",
                "case_sensitive": "on",
            }
        )
        self.assertEqual([pattern["mode"] for pattern in patterns], ["exact", "exact", "regex", "any", "all"])
        self.assertTrue(patterns[0]["case_sensitive"])

    def test_app_renders_homepage(self):
        status_headers = {}

        def start_response(status, headers):
            status_headers["status"] = status
            status_headers["headers"] = headers

        response = b"".join(app({"REQUEST_METHOD": "GET", "PATH_INFO": "/"}, start_response)).decode()
        self.assertIn("Sitemap Word Count UI", response)
        self.assertEqual(status_headers["status"], "200 OK")

    @patch("src.web_ui.WebpageCounter")
    def test_app_handles_analysis_submission(self, counter_cls):
        status_headers = {}
        counter = counter_cls.return_value
        counter.run.return_value = {
            "page_count": 1,
            "totals": {"pricing": {"headings": 2, "body": 3}},
            "pages": [{"url": "https://example.com/page", "headings": {"pricing": 2}, "body": {"pricing": 3}}],
        }
        body = (
            "sitemap_url=https%3A%2F%2Fexample.com%2Fsitemap.xml&"
            "words=pricing&regexes=&any_words=&all_words=&exclude_classes=&output=table"
        ).encode()

        def start_response(status, headers):
            status_headers["status"] = status
            status_headers["headers"] = headers

        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/analyze",
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": __import__("io").BytesIO(body),
        }
        response = b"".join(app(environ, start_response)).decode()
        self.assertIn("Results", response)
        self.assertIn("https://example.com/page", response)
        self.assertEqual(status_headers["status"], "200 OK")


if __name__ == "__main__":
    unittest.main()
