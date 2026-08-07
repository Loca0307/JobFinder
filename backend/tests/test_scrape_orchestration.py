import unittest
import threading
from unittest.mock import Mock, patch

from api.data.schemas import NormalizedJob
from api.services.scrape_orchestration import scrape_sources


def make_job(source: str, country_code: str | None = "CH") -> NormalizedJob:
    return NormalizedJob(
        title=f"Job from {source}",
        country_code=country_code,
        source_website=source,
        source_url=f"https://example.test/{source}/{country_code}",
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

    def test_deduplicates_same_vacancy_across_sources(self):
        self.jobs_ch.scrape.return_value = [
            NormalizedJob(
                title="Senior Python Developer",
                company="Example AG",
                location="Zurich",
                country_code="CH",
                source_website="jobs.ch",
                source_url="https://jobs.ch/job/42",
            )
        ]
        self.swiss_dev.scrape.return_value = [
            NormalizedJob(
                title=" senior  PYTHON developer ",
                company="Example AG",
                location="Zürich",
                country_code="CH",
                source_website="swissdevjobs.ch",
                source_url="https://swissdevjobs.ch/jobs/example-42",
            )
        ]

        result = self.run_sources()

        self.assertEqual(result["jobs_found"], 1)
        self.assertEqual(len(result["jobs"]), 1)
        self.assertEqual(result["jobs"][0]["source_website"], "jobs.ch")
        self.assertEqual(
            {source["jobs_found"] for source in result["sources"]}, {1}
        )

    def test_keeps_same_title_and_company_in_different_locations(self):
        self.jobs_ch.scrape.return_value = [
            NormalizedJob(
                title="Python Developer",
                company="Example AG",
                location="Bern",
                country_code="CH",
                source_website="jobs.ch",
                source_url="https://jobs.ch/job/bern",
            )
        ]
        self.swiss_dev.scrape.return_value = [
            NormalizedJob(
                title="Python Developer",
                company="Example AG",
                location="Zürich",
                country_code="CH",
                source_website="swissdevjobs.ch",
                source_url="https://swissdevjobs.ch/jobs/zurich",
            )
        ]

        result = self.run_sources()

        self.assertEqual(result["jobs_found"], 2)

    def test_returns_only_jobs_with_ch_country_code(self):
        self.jobs_ch.scrape.return_value = [
            make_job("jobs.ch", "CH"),
            make_job("jobs.ch", "DE"),
            make_job("jobs.ch", None),
        ]
        self.swiss_dev.scrape.return_value = []

        result = self.run_sources()

        self.assertEqual(result["jobs_found"], 1)
        self.assertEqual(result["jobs"][0]["country_code"], "CH")

    def test_reports_failed_when_both_sources_fail(self):
        self.jobs_ch.scrape.side_effect = RuntimeError("first")
        self.swiss_dev.scrape.side_effect = RuntimeError("second")
        result = self.run_sources()

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["jobs"], [])
        self.assertEqual(len(result["sources"]), 2)

    def test_uses_each_scraper_default_page_count(self):
        self.jobs_ch.default_pages = 5
        self.swiss_dev.default_pages = 1
        self.jobs_ch.scrape.return_value = []
        self.swiss_dev.scrape.return_value = []

        result = scrape_sources(
            [self.jobs_ch, self.swiss_dev], "python", "Zürich"
        )

        self.assertEqual(result["status"], "completed")
        self.jobs_ch.scrape.assert_called_once_with("python", "Zürich", 5)
        self.swiss_dev.scrape.assert_called_once_with("python", "Zürich", 1)

    def test_limits_concurrent_sources_to_three(self):
        lock = threading.Lock()
        barrier = threading.Barrier(3, timeout=2)
        active = 0
        maximum_active = 0

        def scrape(*args):
            nonlocal active, maximum_active
            with lock:
                active += 1
                maximum_active = max(maximum_active, active)
            barrier.wait()
            with lock:
                active -= 1
            return []

        scrapers = []
        for index in range(6):
            scraper = Mock(
                source_name=f"source-{index}",
                base_url=f"https://source-{index}.test",
                default_pages=1,
            )
            scraper.scrape.side_effect = scrape
            scrapers.append(scraper)

        settings = Mock(scraper_source_max_workers=3)
        with patch(
            "api.services.scrape_orchestration.get_settings",
            return_value=settings,
        ):
            result = scrape_sources(scrapers, "python", "Zürich")

        self.assertEqual(result["status"], "completed")
        self.assertEqual(maximum_active, 3)
        self.assertTrue(all(scraper.scrape.call_count == 1 for scraper in scrapers))


if __name__ == "__main__":
    unittest.main()
