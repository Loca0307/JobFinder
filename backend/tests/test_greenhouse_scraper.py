import json
import unittest

from api.scrapers.ats.greenhouse import GreenhouseScraper
from api.scrapers.ats.targets import GreenhouseTarget
from api.scrapers.base import ScrapeError


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    def get(self, url: str) -> FakeResponse:
        self.urls.append(url)
        return FakeResponse(self.pages[url])

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        pass


def make_target() -> GreenhouseTarget:
    return GreenhouseTarget(
        id="example-greenhouse",
        company_name="Example Greenhouse AG",
        careers_url="https://example.test/careers",
        ats="greenhouse",
        board_token="example",
    )


class GreenhouseScraperTests(unittest.TestCase):
    def test_normalizes_filters_deduplicates_and_skips_prospect_posts(self):
        scraper = GreenhouseScraper(make_target())
        body = json.dumps(
            {
                "jobs": [
                    {
                        "id": 101,
                        "internal_job_id": 501,
                        "title": "Senior Data Engineer",
                        "location": {"name": "Zürich, Switzerland"},
                        "content": (
                            "<p>Build reliable data pipelines &amp; work in a "
                            "hybrid work arrangement using English.</p>"
                        ),
                        "absolute_url": (
                            "https://boards.greenhouse.io/example/jobs/101"
                        ),
                        "metadata": [{"name": "Team", "value": "Data"}],
                    },
                    {
                        "id": 101,
                        "internal_job_id": 501,
                        "title": "Duplicate Data Engineer",
                        "absolute_url": (
                            "https://boards.greenhouse.io/example/jobs/101"
                        ),
                    },
                    {
                        "id": 202,
                        "internal_job_id": 502,
                        "title": "Data Engineer",
                        "location": {"name": "London"},
                        "absolute_url": (
                            "https://boards.greenhouse.io/example/jobs/202"
                        ),
                    },
                    {
                        "id": 999,
                        "internal_job_id": None,
                        "title": "Join our talent community",
                    },
                ]
            }
        )
        client = FakeClient({scraper.jobs_url: body})
        scraper = GreenhouseScraper(make_target(), client_factory=lambda: client)

        jobs = scraper.scrape("data engineer", "Zurich", pages=99)

        self.assertEqual(client.urls, [scraper.jobs_url])
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job.source_website, "company:example-greenhouse")
        self.assertEqual(job.external_id, "101")
        self.assertEqual(job.company, "Example Greenhouse AG")
        self.assertEqual(job.location, "Zürich, Switzerland")
        self.assertEqual(job.country_code, "CH")
        self.assertEqual(
            job.description,
            (
                "Build reliable data pipelines & work in a hybrid work "
                "arrangement using English."
            ),
        )
        self.assertEqual(job.seniority, "senior")
        self.assertEqual(job.remote_type, "hybrid")
        self.assertEqual(job.required_languages, ["English"])
        self.assertTrue(job.details_loaded)
        self.assertEqual(job.raw_payload["parser"], "greenhouse_api")
        self.assertEqual(job.raw_payload["target_id"], "example-greenhouse")

    def test_excludes_unmatched_keyword_and_location(self):
        scraper = GreenhouseScraper(make_target())
        body = json.dumps(
            {
                "jobs": [
                    {
                        "id": 101,
                        "title": "Python Engineer",
                        "location": {"name": "Zürich, Switzerland"},
                        "absolute_url": (
                            "https://boards.greenhouse.io/example/jobs/101"
                        ),
                    }
                ]
            }
        )

        def search(term: str, location: str) -> list:
            client = FakeClient({scraper.jobs_url: body})
            return GreenhouseScraper(
                make_target(), client_factory=lambda: client
            ).scrape(term, location)

        self.assertEqual(len(search("python", "Zurich")), 1)
        self.assertEqual(search("java", "Zurich"), [])
        self.assertEqual(search("python", "Geneva"), [])

    def test_accepts_empty_or_prospect_only_boards(self):
        scraper = GreenhouseScraper(make_target())

        self.assertEqual(scraper._parse_jobs('{"jobs": []}'), [])
        self.assertEqual(
            scraper._parse_jobs('{"jobs": [{"id": 1, "internal_job_id": null}]}'),
            [],
        )

    def test_leaves_foreign_location_unclassified(self):
        job = GreenhouseScraper(make_target())._normalize(
            {
                "id": 202,
                "title": "Data Engineer",
                "location": {"name": "London"},
                "absolute_url": "https://boards.greenhouse.io/example/jobs/202",
            }
        )

        self.assertIsNotNone(job)
        self.assertIsNone(job.country_code)

    def test_rejects_malformed_or_unusable_payloads(self):
        cases = (
            ("not-json", "malformed"),
            ('{"jobs": {}}', "must be a list"),
            ('{"jobs": [{"internal_job_id": 2}]}', "no usable jobs"),
        )

        for body, message in cases:
            with self.subTest(body=body), self.assertRaisesRegex(ScrapeError, message):
                GreenhouseScraper(make_target())._parse_jobs(body)


if __name__ == "__main__":
    unittest.main()
