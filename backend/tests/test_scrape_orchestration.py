import unittest
from unittest.mock import Mock, patch

from api.data.schemas import NormalizedJob
from api.services.scrape_orchestration import scrape_sources


def make_job(source: str) -> NormalizedJob:
    return NormalizedJob(
        title=f"Job from {source}",
        source_website=source,
        source_url=f"https://example.test/{source}",
    )


class ScrapeOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.jobs_ch = Mock(source_name="jobs.ch", base_url="https://www.jobs.ch")
        self.swiss_dev = Mock(
            source_name="swissdevjobs.ch", base_url="https://swissdevjobs.ch"
        )

    def run_sources(self):
        return scrape_sources(
            [self.jobs_ch, self.swiss_dev],
            "python",
            "Zürich",
            {"jobs.ch": 5, "swissdevjobs.ch": 5},
        )

    def test_combines_successful_sources_without_database_writes(self):
        self.jobs_ch.scrape.return_value = [make_job("jobs.ch")]
        self.swiss_dev.scrape.return_value = [make_job("swissdevjobs.ch")]

        result = self.run_sources()

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["jobs_found"], 2)
        self.assertNotIn("jobs_created", result)
        self.assertNotIn("jobs_updated", result)
        self.assertEqual(len(result["jobs"]), 2)
        self.assertEqual(
            {job["source_website"] for job in result["jobs"]},
            {"jobs.ch", "swissdevjobs.ch"},
        )
        self.swiss_dev.scrape.assert_called_once_with("python", "Zürich", 5)

    def test_returns_partial_success_and_keeps_valid_jobs(self):
        self.jobs_ch.scrape.side_effect = RuntimeError("jobs.ch unavailable")
        self.swiss_dev.scrape.return_value = [make_job("swissdevjobs.ch")]
        result = self.run_sources()

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["jobs_found"], 1)
        self.assertEqual(len(result["jobs"]), 1)
        failed = next(source for source in result["sources"] if source["status"] == "failed")
        self.assertEqual(failed["source_id"], "jobs.ch")
        self.assertIn("unavailable", failed["error_message"])

    def test_reports_failed_when_both_sources_fail(self):
        self.jobs_ch.scrape.side_effect = RuntimeError("first")
        self.swiss_dev.scrape.side_effect = RuntimeError("second")
        result = self.run_sources()

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["jobs"], [])
        self.assertEqual(len(result["sources"]), 2)


if __name__ == "__main__":
    unittest.main()
