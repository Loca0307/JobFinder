import unittest

from api.scrapers.registry import (
    get_all_scrapers,
    get_detail_scraper,
    get_scraper,
)


class ScraperRegistryTests(unittest.TestCase):
    def test_returns_all_enabled_scrapers(self):
        self.assertEqual(
            {scraper.source_name for scraper in get_all_scrapers()},
            {"jobs.ch", "jobup.ch", "swissdevjobs.ch"},
        )

    def test_resolves_scraper_by_canonical_source_name(self):
        scraper = get_scraper("JOBS.CH")

        self.assertIsNotNone(scraper)
        self.assertEqual(scraper.source_name, "jobs.ch")

    def test_returns_none_for_unknown_source(self):
        self.assertIsNone(get_scraper("unknown.example"))

    def test_only_returns_detail_capable_scrapers(self):
        self.assertIsNotNone(get_detail_scraper("jobs.ch"))
        self.assertIsNotNone(get_detail_scraper("jobup.ch"))
        self.assertIsNone(get_detail_scraper("swissdevjobs.ch"))


if __name__ == "__main__":
    unittest.main()
