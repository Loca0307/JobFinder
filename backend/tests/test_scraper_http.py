import unittest
from unittest.mock import Mock

from api.scrapers.http import (
    RequestRateLimiter,
    ScraperHttpClient,
    ScraperHttpConfig,
)


class RequestRateLimiterTests(unittest.TestCase):
    def test_spaces_requests_at_configured_rate(self):
        current_time = [10.0]
        delays: list[float] = []

        def sleep_and_advance(delay: float) -> None:
            delays.append(delay)
            current_time[0] += delay

        limiter = RequestRateLimiter(
            requests_per_second=2,
            clock=lambda: current_time[0],
            sleeper=sleep_and_advance,
        )

        limiter.wait()
        limiter.wait()
        limiter.wait()

        self.assertEqual(delays, [0.5, 0.5])

    def test_zero_rate_disables_waiting(self):
        sleeper = Mock()
        limiter = RequestRateLimiter(requests_per_second=0, sleeper=sleeper)

        limiter.wait()

        sleeper.assert_not_called()


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

    def test_get_waits_for_rate_limiter_before_request(self):
        events: list[str] = []
        rate_limiter = Mock()
        rate_limiter.wait.side_effect = lambda: events.append("wait")
        client = ScraperHttpClient(self.config, rate_limiter)
        response = Mock()
        client.session.get = Mock(
            side_effect=lambda *args, **kwargs: events.append("get") or response
        )

        client.get("https://example.test/jobs")

        self.assertEqual(events, ["wait", "get"])
        client.close()

    def test_context_manager_closes_session(self):
        client = ScraperHttpClient(self.config)
        client.session.close = Mock()

        with client as entered_client:
            self.assertIs(entered_client, client)

        client.session.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
