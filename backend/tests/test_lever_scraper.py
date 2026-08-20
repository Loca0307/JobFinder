import json
import unittest

from api.scrapers.ats.lever import PAGE_SIZE, LeverScraper
from api.scrapers.ats.targets import LeverTarget
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


def make_target(region: str = "eu") -> LeverTarget:
    return LeverTarget(
        id="example-lever",
        company_name="Example Lever AG",
        careers_url="https://example.test/jobs",
        ats="lever",
        site="example",
        region=region,
    )


def posting(source_id: str) -> dict[str, object]:
    return {
        "id": source_id,
        "text": f"Job {source_id}",
        "hostedUrl": f"https://jobs.lever.co/example/{source_id}",
    }


class LeverScraperTests(unittest.TestCase):
    def test_normalizes_fields_and_applies_local_search_filters(self):
        scraper = LeverScraper(make_target())
        item = {
            "id": "lever-1",
            "text": "Senior Platform Engineer",
            "country": "CH",
            "categories": {
                "allLocations": ["Zürich", "Remote - Switzerland", "Zürich"],
                "commitment": "Full-time",
            },
            "descriptionPlain": "Build and operate the platform in English.",
            "description": "<p>Duplicate HTML description.</p>",
            "lists": [
                {
                    "text": "What you must have",
                    "content": "<p>Python<br>AWS</p>",
                }
            ],
            "workplaceType": "hybrid",
            "salaryRange": {
                "min": 120000,
                "max": 140000,
                "currency": "CHF",
                "interval": "year",
            },
            "hostedUrl": "https://jobs.eu.lever.co/example/lever-1",
            "applyUrl": "https://jobs.eu.lever.co/example/lever-1/apply",
        }
        client = FakeClient({scraper._page_url(0): json.dumps([item])})
        scraper = LeverScraper(make_target(), client_factory=lambda: client)

        jobs = scraper.scrape("platform engineer", "Switzerland")

        self.assertEqual(client.urls, [scraper._page_url(0)])
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job.source_website, "company:example-lever")
        self.assertEqual(job.external_id, "lever-1")
        self.assertEqual(job.company, "Example Lever AG")
        self.assertEqual(job.location, "Zürich, Remote - Switzerland")
        self.assertEqual(job.country_code, "CH")
        self.assertEqual(job.requirements, "Python\nAWS")
        self.assertIn("What you must have\n\nPython\nAWS", job.description)
        self.assertEqual(job.employment_type, "Full-time")
        self.assertEqual(job.remote_type, "hybrid")
        self.assertEqual(job.salary, "CHF 120000\u2013140000 per year")
        self.assertEqual(job.required_languages, ["English"])
        self.assertEqual(job.raw_payload["parser"], "lever_api")
        self.assertEqual(job.raw_payload["target_id"], "example-lever")

    def test_searches_all_list_sections_and_excludes_nonmatches(self):
        scraper = LeverScraper(make_target())
        item = {
            **posting("list-search"),
            "country": "CH",
            "categories": {"location": "Zürich"},
            "descriptionPlain": "Build autonomous robots.",
            "lists": [
                {
                    "text": "Get some bonus points",
                    "content": "<ul><li>Python</li></ul>",
                }
            ],
        }
        body = json.dumps([item])

        def search(term: str, location: str) -> list:
            client = FakeClient({scraper._page_url(0): body})
            return LeverScraper(make_target(), client_factory=lambda: client).scrape(
                term, location
            )

        self.assertEqual(len(search("python", "Switzerland")), 1)
        self.assertEqual(search("java", "Switzerland"), [])
        self.assertEqual(search("python", "Geneva"), [])

    def test_builds_global_and_eu_urls(self):
        self.assertTrue(
            LeverScraper(make_target("global"))
            ._page_url(0)
            .startswith("https://api.lever.co/v0/postings/example?")
        )
        eu_url = LeverScraper(make_target("eu"))._page_url(1)
        self.assertTrue(
            eu_url.startswith("https://api.eu.lever.co/v0/postings/example?")
        )
        self.assertIn("skip=100", eu_url)

    def test_structured_country_takes_precedence(self):
        item = posting("foreign")
        item.update(
            {
                "country": "GB",
                "categories": {"location": "Zürich"},
            }
        )

        job = LeverScraper(make_target())._normalize(item)

        self.assertIsNotNone(job)
        self.assertEqual(job.country_code, "GB")

    def test_paginates_and_deduplicates_overlapping_ids(self):
        scraper = LeverScraper(make_target())
        first_page = [posting(str(index)) for index in range(PAGE_SIZE)]
        second_page = [posting("99"), posting("100")]
        client = FakeClient(
            {
                scraper._page_url(0): json.dumps(first_page),
                scraper._page_url(1): json.dumps(second_page),
            }
        )
        scraper = LeverScraper(make_target(), client_factory=lambda: client)

        jobs = scraper.scrape(pages=2)

        self.assertEqual(len(jobs), 101)
        self.assertEqual(jobs[-1].external_id, "100")

    def test_repeated_page_fails_loudly(self):
        scraper = LeverScraper(make_target())
        page = json.dumps([posting(str(index)) for index in range(PAGE_SIZE)])
        client = FakeClient({scraper._page_url(0): page, scraper._page_url(1): page})

        with self.assertRaisesRegex(ScrapeError, "repeated page"):
            LeverScraper(make_target(), client_factory=lambda: client).scrape(pages=2)

    def test_rejects_malformed_payloads(self):
        cases = (
            ("not-json", "malformed"),
            ('{"jobs": []}', "must be a list"),
            ("[1, 2]", "contain no objects"),
        )

        for body, message in cases:
            with self.subTest(body=body), self.assertRaisesRegex(ScrapeError, message):
                LeverScraper(make_target())._parse_page(body)

    def test_page_limit_fails_loudly(self):
        scraper = LeverScraper(make_target())
        page = json.dumps([posting(str(index)) for index in range(PAGE_SIZE)])
        overflow = json.dumps([posting("overflow")])
        client = FakeClient(
            {
                scraper._page_url(0): page,
                scraper._page_url(1): overflow,
            }
        )

        with self.assertRaisesRegex(ScrapeError, "page limit"):
            LeverScraper(make_target(), client_factory=lambda: client).scrape(pages=1)

    def test_exactly_full_last_page_is_not_treated_as_truncated(self):
        scraper = LeverScraper(make_target())
        page = json.dumps([posting(str(index)) for index in range(PAGE_SIZE)])
        client = FakeClient(
            {
                scraper._page_url(0): page,
                scraper._page_url(1): "[]",
            }
        )

        jobs = LeverScraper(make_target(), client_factory=lambda: client).scrape(
            pages=1
        )

        self.assertEqual(len(jobs), PAGE_SIZE)


if __name__ == "__main__":
    unittest.main()
