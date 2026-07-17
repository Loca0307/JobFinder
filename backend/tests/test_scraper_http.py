import unittest
from unittest.mock import Mock

from api.scrapers.http import ScraperHttpClient, ScraperHttpConfig


class ScraperHttpClientTests(unittest.TestCase):
    def setUp(self):
        self.config = ScraperHttpConfig(
            user_agent="JobFinderTests/1.0",
            accept_language="en-CH",
            connect_timeout=2,
            read_timeout=7,
            max_retries=4,
            backoff_factor=0.5,
        )
        self.client = ScraperHttpClient(self.config)

    def tearDown(self):
        self.client.close()

    def test_session_uses_configured_headers(self):
        self.assertEqual(
            self.client.session.headers["User-Agent"], "JobFinderTests/1.0"
        )
        self.assertEqual(self.client.session.headers["Accept-Language"], "en-CH")

    def test_http_and_https_use_retry_policy(self):
        for scheme in ("http://", "https://"):
            with self.subTest(scheme=scheme):
                retry = self.client.session.get_adapter(scheme).max_retries
                self.assertEqual(retry.total, 4)
                self.assertEqual(retry.backoff_factor, 0.5)
                self.assertEqual(
                    retry.status_forcelist, (429, 500, 502, 503, 504)
                )
                self.assertEqual(retry.allowed_methods, {"GET"})
                self.assertTrue(retry.respect_retry_after_header)

    def test_get_applies_timeouts_and_checks_http_status(self):
        response = Mock()
        self.client.session.get = Mock(return_value=response)

        returned_response = self.client.get("https://example.test/jobs")

        self.assertIs(returned_response, response)
        self.client.session.get.assert_called_once_with(
            "https://example.test/jobs", timeout=(2, 7)
        )
        response.raise_for_status.assert_called_once_with()

    def test_context_manager_closes_session(self):
        client = ScraperHttpClient(self.config)
        client.session.close = Mock()

        with client as entered_client:
            self.assertIs(entered_client, client)

        client.session.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
