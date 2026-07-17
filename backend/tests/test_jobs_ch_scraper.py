import json
import unittest
from unittest.mock import Mock, patch

import requests

from api.scrapers.jobs_ch import JobsChScraper, _beautiful_soup


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

    def test_extract_detail_urls_supports_languages_cleans_and_deduplicates(self):
        html = """
        <main>
          <a href="/en/vacancies/detail/example-id/?ref=first">First</a>
          <a href="/en/vacancies/detail/example-id/?ref=duplicate">Duplicate</a>
          <a href="https://www.jobs.ch/de/stellenangebote/detail/zweite-id/">Second</a>
          <a href="/fr/offres-emplois/detail/troisieme-id/?source=list">Third</a>
          <a href="/en/vacancies/?page=2">Pagination, not a job</a>
        </main>
        """

        self.assertEqual(
            self.scraper._extract_detail_urls(html),
            [
                "https://www.jobs.ch/en/vacancies/detail/example-id/",
                "https://www.jobs.ch/de/stellenangebote/detail/zweite-id/",
                "https://www.jobs.ch/fr/offres-emplois/detail/troisieme-id/",
            ],
        )

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
        self.scraper.session.get = Mock(return_value=response)

        job = self.scraper._scrape_detail(
            "https://www.jobs.ch/en/vacancies/detail/fallback/"
        )

        self.assertIsNotNone(job)
        self.assertEqual(job.title, "Junior Backend Developer")
        self.assertEqual(job.seniority, "junior")
        self.assertEqual(job.remote_type, "hybrid")
        self.assertEqual(job.required_languages, ["English"])
        self.assertEqual(job.raw_payload, {"parser": "html_fallback"})

    def test_scrape_deduplicates_across_pages_and_isolates_detail_failures(self):
        listing_response = Mock()
        listing_response.text = "<html></html>"
        listing_response.raise_for_status.return_value = None
        self.scraper.session.get = Mock(return_value=listing_response)

        first_job = Mock()
        with (
            patch.object(
                self.scraper,
                "_extract_detail_urls",
                side_effect=[
                    ["https://example.test/job/1", "https://example.test/job/2"],
                    ["https://example.test/job/1", "https://example.test/job/3"],
                ],
            ),
            patch.object(
                self.scraper,
                "_scrape_detail",
                side_effect=[first_job, requests.Timeout("slow detail"), None],
            ) as scrape_detail,
        ):
            jobs = self.scraper.scrape(pages=2)

        self.assertEqual(jobs, [first_job])
        self.assertEqual(
            [call.args[0] for call in scrape_detail.call_args_list],
            [
                "https://example.test/job/1",
                "https://example.test/job/2",
                "https://example.test/job/3",
            ],
        )

    def test_scrape_continues_after_a_listing_request_failure(self):
        failed_response = Mock()
        failed_response.raise_for_status.side_effect = requests.HTTPError("503")
        successful_response = Mock()
        successful_response.text = "<html></html>"
        successful_response.raise_for_status.return_value = None
        self.scraper.session.get = Mock(
            side_effect=[failed_response, successful_response]
        )

        with patch.object(
            self.scraper, "_extract_detail_urls", return_value=[]
        ) as extract_urls:
            jobs = self.scraper.scrape(pages=2)

        self.assertEqual(jobs, [])
        extract_urls.assert_called_once_with("<html></html>")


if __name__ == "__main__":
    unittest.main()
