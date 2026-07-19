import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from api.data.models import job_id
from api.data.schemas import NormalizedJob
from api.routes.jobs import get_job_detail


class JobDetailRouteTests(unittest.TestCase):
    def setUp(self):
        self.job = NormalizedJob(
            title="Python Developer",
            source_website="jobs.ch",
            source_url="https://www.jobs.ch/en/vacancies/detail/job-42/",
            external_id="job-42",
        )
        self.scraper = Mock(source_name="jobs.ch")

    def test_delegates_to_source_detail_scraper(self):
        self.scraper.scrape_detail.return_value = self.job

        with (
            patch("api.routes.jobs.get_scraper", return_value=self.scraper),
            patch("api.routes.jobs.get_detail_scraper", return_value=self.scraper),
        ):
            result = get_job_detail("jobs.ch", "job-42")

        self.scraper.scrape_detail.assert_called_once_with("job-42")
        self.assertEqual(
            result["id"],
            job_id(self.job.source_website, str(self.job.source_url)),
        )
        self.assertEqual(result["external_id"], "job-42")

    def test_rejects_unknown_source(self):
        with patch("api.routes.jobs.get_scraper", return_value=None):
            with self.assertRaises(HTTPException) as raised:
                get_job_detail("unknown.example", "job-42")

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "Unknown job source")

    def test_rejects_source_without_detail_support(self):
        with (
            patch("api.routes.jobs.get_scraper", return_value=self.scraper),
            patch("api.routes.jobs.get_detail_scraper", return_value=None),
        ):
            with self.assertRaises(HTTPException) as raised:
                get_job_detail("swissdevjobs.ch", "job-42")

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(
            raised.exception.detail,
            "Job source does not support detail loading",
        )

    def test_returns_bad_request_for_invalid_external_id(self):
        self.scraper.scrape_detail.side_effect = ValueError("Invalid job ID")

        with (
            patch("api.routes.jobs.get_scraper", return_value=self.scraper),
            patch("api.routes.jobs.get_detail_scraper", return_value=self.scraper),
        ):
            with self.assertRaises(HTTPException) as raised:
                get_job_detail("jobs.ch", "invalid")

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "Invalid job ID")

    def test_returns_not_found_when_vacancy_is_missing(self):
        self.scraper.scrape_detail.return_value = None

        with (
            patch("api.routes.jobs.get_scraper", return_value=self.scraper),
            patch("api.routes.jobs.get_detail_scraper", return_value=self.scraper),
        ):
            with self.assertRaises(HTTPException) as raised:
                get_job_detail("jobs.ch", "missing")

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "Job not found")

    def test_hides_upstream_failure_details(self):
        self.scraper.scrape_detail.side_effect = RuntimeError("private upstream error")

        with (
            patch("api.routes.jobs.get_scraper", return_value=self.scraper),
            patch("api.routes.jobs.get_detail_scraper", return_value=self.scraper),
        ):
            with self.assertRaises(HTTPException) as raised:
                get_job_detail("jobs.ch", "job-42")

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(raised.exception.detail, "Job detail request failed")


if __name__ == "__main__":
    unittest.main()
