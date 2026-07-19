import json
import threading
import unittest
from unittest.mock import MagicMock, Mock, patch

import requests

from api.scrapers.jobs_ch import (
    JobsChScraper,
    _beautiful_soup,
    get_jobs_ch_scraper,
)


class JobsChScraperTests(unittest.TestCase):
    def setUp(self):
        self.scraper = JobsChScraper()

    def test_build_listing_url_encodes_filters_and_normalizes_location(self):
        url = self.scraper._build_listing_url(
            search_term="Python developer",
            location="Zurigo",
            page=3,
        )

        self.assertEqual(
            url,
            "https://www.jobs.ch/en/vacancies/"
            "?term=Python%20developer&location=Z%C3%BCrich&page=3",
        )

    def test_build_listing_url_omits_empty_filters_and_first_page_number(self):
        self.assertEqual(
            self.scraper._build_listing_url(None, None, 1),
            "https://www.jobs.ch/en/vacancies/",
        )

    def test_extract_listing_jobs_returns_incomplete_summaries(self):
        state = {
            "vacancy": {
                "results": {
                    "main": {
                        "results": [
                            {
                                "id": "job-42",
                                "title": "Python Developer",
                                "company": {"name": "Example AG"},
                                "place": "Zürich",
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
        self.assertEqual(jobs[0].title, "Python Developer")
        self.assertEqual(jobs[0].company, "Example AG")
        self.assertEqual(jobs[0].location, "Zürich")
        self.assertEqual(jobs[0].external_id, "job-42")
        self.assertFalse(jobs[0].details_loaded)

    def test_extract_job_posting_json_skips_malformed_scripts(self):
        valid_payload = {"@type": "JobPosting", "title": "Backend Engineer"}
        soup = _beautiful_soup(
            "<script type='application/ld+json'>{bad json</script>"
            f"<script type='application/ld+json'>{json.dumps(valid_payload)}</script>"
        )

        self.assertEqual(
            self.scraper._extract_job_posting_json(soup), valid_payload
        )

    def test_from_json_ld_normalizes_structured_job_fields(self):
        payload = {
            "@type": "JobPosting",
            "title": "Senior Python Engineer",
            "hiringOrganization": {"name": "Example AG"},
            "jobLocation": [
                {
                    "address": {
                        "addressLocality": "Zürich",
                        "addressCountry": "CH",
                    }
                },
                {"address": {"addressLocality": "Bern"}},
            ],
            "description": "<p>Fluent English. Hybrid work available.</p>",
            "qualifications": ["Python", "FastAPI"],
            "employmentType": ["FULL_TIME", "PERMANENT"],
            "jobLocationType": "TELECOMMUTE",
            "baseSalary": {
                "currency": "CHF",
                "value": {
                    "minValue": 100000,
                    "maxValue": 120000,
                    "unitText": "YEAR",
                },
            },
            "datePosted": "2026-07-10T08:30:00Z",
            "identifier": {"value": "job-42"},
        }

        job = self.scraper._from_json_ld(
            payload, "https://www.jobs.ch/en/vacancies/detail/job-42/"
        )

        self.assertEqual(job.title, "Senior Python Engineer")
        self.assertEqual(job.company, "Example AG")
        self.assertEqual(job.location, "Zürich, CH; Bern")
        self.assertEqual(job.description, "Fluent English. Hybrid work available.")
        self.assertEqual(job.requirements, "Python FastAPI")
        self.assertEqual(job.seniority, "senior")
        self.assertEqual(job.employment_type, "FULL_TIME, PERMANENT")
        self.assertEqual(job.remote_type, "remote")
        self.assertEqual(job.salary, "CHF 100000 - 120000 YEAR")
        self.assertEqual(job.required_languages, ["English"])
        self.assertEqual(job.external_id, "job-42")
        self.assertEqual(job.posting_date.isoformat(), "2026-07-10T08:30:00+00:00")

    def test_scrape_detail_uses_html_fallback_when_json_ld_is_absent(self):
        response = Mock()
        response.text = """
        <html>
          <main>
            <h1>Junior Backend Developer</h1>
            <section data-cy="job-description">
              English is required. This is a hybrid role.
            </section>
          </main>
        </html>
        """
        response.raise_for_status.return_value = None
        client = Mock()
        client.get.return_value = response

        job = self.scraper._scrape_detail(
            "https://www.jobs.ch/en/vacancies/detail/fallback/", client
        )

        self.assertIsNotNone(job)
        self.assertEqual(job.title, "Junior Backend Developer")
        self.assertEqual(job.seniority, "junior")
        self.assertEqual(job.remote_type, "hybrid")
        self.assertEqual(job.required_languages, ["English"])
        self.assertEqual(job.raw_payload, {"parser": "html_fallback"})

    def test_scrape_page_does_not_fetch_job_details(self):
        listing_response = Mock()
        listing_response.text = "<html></html>"
        listing_response.raise_for_status.return_value = None
        client = MagicMock()
        client.__enter__.return_value = client
        client.get.return_value = listing_response

        summary_job = Mock()
        with (
            patch.object(self.scraper, "_create_http_client", return_value=client),
            patch.object(
                self.scraper,
                "_extract_listing_jobs",
                return_value=[summary_job],
            ) as extract_summaries,
        ):
            page, jobs = self.scraper._scrape_page(None, None, 2)

        self.assertEqual(page, 2)
        self.assertEqual(jobs, [summary_job])
        extract_summaries.assert_called_once_with(listing_response.text)
        client.get.assert_called_once()
        client.__exit__.assert_called_once()

    def test_public_detail_method_builds_url_and_reuses_parser(self):
        client = MagicMock()
        client.__enter__.return_value = client
        detailed_job = Mock()

        with (
            patch.object(self.scraper, "_create_http_client", return_value=client),
            patch.object(self.scraper, "_scrape_detail", return_value=detailed_job) as scrape,
        ):
            result = self.scraper.scrape_detail("job-42")

        self.assertIs(result, detailed_job)
        scrape.assert_called_once_with(
            "https://www.jobs.ch/en/vacancies/detail/job-42/", client
        )

    def test_scrape_page_propagates_listing_failure(self):
        client = MagicMock()
        client.__enter__.return_value = client
        client.get.side_effect = requests.HTTPError("503")

        with patch.object(self.scraper, "_create_http_client", return_value=client):
            with self.assertRaises(requests.HTTPError):
                self.scraper._scrape_page(None, None, 4)

    def test_scrape_runs_five_pages_concurrently(self):
        barrier = threading.Barrier(5, timeout=2)
        visited_pages: list[int] = []
        visited_lock = threading.Lock()

        def scrape_page(search_term, location, page):
            with visited_lock:
                visited_pages.append(page)
            barrier.wait()
            return page, []

        with patch.object(self.scraper, "_scrape_page", side_effect=scrape_page):
            jobs = self.scraper.scrape("python", "Zürich", pages=5)

        self.assertEqual(jobs, [])
        self.assertEqual(sorted(visited_pages), [1, 2, 3, 4, 5])

    def test_scrape_defaults_to_five_pages(self):
        visited_pages: list[int] = []

        def scrape_page(search_term, location, page):
            visited_pages.append(page)
            return page, []

        with patch.object(self.scraper, "_scrape_page", side_effect=scrape_page):
            self.scraper.scrape()

        self.assertEqual(sorted(visited_pages), [1, 2, 3, 4, 5])

    def test_scrape_merges_in_page_order_and_deduplicates_across_pages(self):
        first = Mock(source_url="https://example.test/job/1")
        duplicate = Mock(source_url="https://example.test/job/1")
        second = Mock(source_url="https://example.test/job/2")

        def scrape_page(search_term, location, page):
            if page == 1:
                return 1, [first]
            return 2, [duplicate, second]

        with patch.object(self.scraper, "_scrape_page", side_effect=scrape_page):
            jobs = self.scraper.scrape(pages=2)

        self.assertEqual(jobs, [first, second])

    def test_scrape_isolates_unexpected_page_worker_failure(self):
        surviving_job = Mock(source_url="https://example.test/job/survives")

        def scrape_page(search_term, location, page):
            if page == 1:
                raise RuntimeError("worker crashed")
            return page, [surviving_job]

        with patch.object(self.scraper, "_scrape_page", side_effect=scrape_page):
            jobs = self.scraper.scrape(pages=2)

        self.assertEqual(jobs, [surviving_job])

    def test_scrape_fails_when_every_page_fails(self):
        with patch.object(
            self.scraper, "_scrape_page", side_effect=requests.HTTPError("503")
        ):
            with self.assertRaisesRegex(RuntimeError, "All 2 requested pages failed"):
                self.scraper.scrape(pages=2)

    def test_each_created_http_client_is_independent(self):
        first = self.scraper._create_http_client()
        second = self.scraper._create_http_client()

        self.assertIsNot(first, second)
        self.assertIsNot(first.session, second.session)
        self.assertIs(first.rate_limiter, second.rate_limiter)
        first.close()
        second.close()

    def test_cached_factory_reuses_one_scraper_instance(self):
        get_jobs_ch_scraper.cache_clear()

        first = get_jobs_ch_scraper()
        second = get_jobs_ch_scraper()

        self.assertIs(first, second)
        get_jobs_ch_scraper.cache_clear()


if __name__ == "__main__":
    unittest.main()
