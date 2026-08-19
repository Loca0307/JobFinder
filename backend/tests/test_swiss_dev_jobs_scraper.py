import unittest
from unittest.mock import MagicMock, patch

from api.scrapers.swiss_dev_jobs import SwissDevJobsScraper


FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title><![CDATA[Senior Platform Engineer @ Example AG [CHF 115'000 - 130'000]]]></title>
    <link>https://swissdevjobs.ch/jobs/example?utm_source=rss&amp;ref=keep</link>
    <guid>example-1</guid>
    <pubDate>Fri, 20 Mar 2026 23:00:00 GMT</pubDate>
    <description><![CDATA[
      <p><b>Salary: CHF 115'000 - 130'000 per year</b></p>
      <b>Requirements:</b><ul><li>Fluent German and good English.</li></ul>
      <b>Responsibilities:</b><ul><li>Build platforms in Zürich with the possibility for home office.</li></ul>
      <b>Technologies:</b><ul><li>Python</li><li>Kubernetes</li></ul>
      <b>More:</b><p>Join our engineering team.</p>
    ]]></description>
  </item>
  <item>
    <title>Backend Engineer @ Other AG [CHF 90'000 - 100'000]</title>
    <link>https://swissdevjobs.ch/jobs/other</link>
    <description><![CDATA[<b>Responsibilities:</b><p>Work in Bern using Go.</p>]]></description>
  </item>
</channel></rss>"""


class SwissDevJobsScraperTests(unittest.TestCase):
    def setUp(self):
        self.scraper = SwissDevJobsScraper()

    def test_parses_and_normalizes_rss_job(self):
        jobs = self.scraper._parse_feed(FEED)

        self.assertEqual(len(jobs), 2)
        self.assertTrue(all(job.country_code == "CH" for job in jobs))
        job = jobs[0]
        self.assertEqual(job.title, "Senior Platform Engineer")
        self.assertEqual(job.company, "Example AG")
        self.assertEqual(job.salary, "CHF 115'000 - 130'000")
        self.assertEqual(job.requirements, "Fluent German and good English.")
        self.assertIn("Python Kubernetes", job.description)
        self.assertEqual(job.seniority, "senior")
        self.assertEqual(job.remote_type, "hybrid")
        self.assertEqual(job.required_languages, ["English", "German"])
        self.assertEqual(job.posting_date.isoformat(), "2026-03-20T23:00:00+00:00")
        self.assertEqual(
            str(job.source_url), "https://swissdevjobs.ch/jobs/example?ref=keep"
        )
        self.assertEqual(job.source_website, "swissdevjobs.ch")

    def test_filters_keyword_and_normalized_location_locally(self):
        jobs = self.scraper._parse_feed(FEED, "python", "Zurigo")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].location, "Zürich")

    def test_excludes_entry_without_location_evidence(self):
        self.assertEqual(self.scraper._parse_feed(FEED, location="Lugano"), [])

    def test_deduplicates_canonical_urls(self):
        duplicate = FEED.replace(
            "</channel>",
            """<item><title>Duplicate @ Example AG [CHF 1 - 2]</title>
            <link>https://swissdevjobs.ch/jobs/example?ref=keep&amp;utm_medium=x</link>
            <description>Duplicate</description></item></channel>""",
        )

        self.assertEqual(len(self.scraper._parse_feed(duplicate)), 2)

    def test_scrape_fetches_the_feed_once(self):
        response = MagicMock(text=FEED)
        client = MagicMock()
        client.__enter__.return_value = client
        client.get.return_value = response

        with patch.object(self.scraper, "_create_http_client", return_value=client):
            jobs = self.scraper.scrape("python", "Zürich", pages=10)

        self.assertEqual(len(jobs), 1)
        client.get.assert_called_once_with("https://swissdevjobs.ch/rss")
        client.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
