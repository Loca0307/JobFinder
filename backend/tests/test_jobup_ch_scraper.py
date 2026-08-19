import json
import unittest
from unittest.mock import MagicMock, patch

from api.scrapers.jobup_ch import JobupChScraper, get_jobup_ch_scraper


class JobupChScraperTests(unittest.TestCase):
    def setUp(self):
        self.scraper = JobupChScraper()

    def test_build_listing_url_uses_jobup_paths_and_filters(self):
        self.assertEqual(
            self.scraper._build_listing_url("Python developer", "Lausanne", 2),
            "https://www.jobup.ch/en/jobs/"
            "?term=Python%20developer&location=Lausanne&page=2",
        )

    def test_extract_listing_jobs_builds_jobup_summary_url(self):
        state = {
            "vacancy": {
                "results": {
                    "main": {
                        "results": [
                            {
                                "id": "job-42",
                                "title": "Python Developer",
                                "company": {"name": "Example SA"},
                                "place": "Lausanne",
                                "publicationDate": "2026-07-10T08:30:00Z",
                            }
                        ]
                    }
                }
            }
        }

        jobs = self.scraper._extract_listing_jobs(
            f"<script>__INIT__ = {json.dumps(state)};</script>"
        )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source_website, "jobup.ch")
        self.assertEqual(jobs[0].country_code, "CH")
        self.assertEqual(
            str(jobs[0].source_url),
            "https://www.jobup.ch/en/jobs/detail/job-42/",
        )
        self.assertFalse(jobs[0].details_loaded)

    def test_public_detail_method_uses_jobup_detail_path(self):
        client = MagicMock()
        client.__enter__.return_value = client
        detailed_job = MagicMock()

        with (
            patch.object(self.scraper, "_create_http_client", return_value=client),
            patch.object(
                self.scraper, "_scrape_detail", return_value=detailed_job
            ) as scrape,
        ):
            result = self.scraper.scrape_detail("job-42")

        self.assertIs(result, detailed_job)
        scrape.assert_called_once_with(
            "https://www.jobup.ch/en/jobs/detail/job-42/", client
        )

    def test_cached_factory_reuses_one_scraper_instance(self):
        get_jobup_ch_scraper.cache_clear()

        first = get_jobup_ch_scraper()
        second = get_jobup_ch_scraper()

        self.assertIs(first, second)
        get_jobup_ch_scraper.cache_clear()


if __name__ == "__main__":
    unittest.main()
