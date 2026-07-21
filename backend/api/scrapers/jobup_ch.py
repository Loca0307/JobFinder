from __future__ import annotations

from functools import lru_cache

from api.scrapers.jobs_ch import JobsChScraper


class JobupChScraper(JobsChScraper):
    """Scrape jobup.ch through the shared JobCloud page structure."""

    source_name = "jobup.ch"
    base_url = "https://www.jobup.ch"
    listing_path = "/en/jobs/"
    detail_path = "/en/jobs/detail/"


@lru_cache(maxsize=1)
def get_jobup_ch_scraper() -> JobupChScraper:
    """Return the single jobup.ch scraper used by this backend process."""
    return JobupChScraper()
