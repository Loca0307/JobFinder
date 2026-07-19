from __future__ import annotations

from collections.abc import Callable

from api.scrapers.base import BaseJobScraper, DetailJobScraper
from api.scrapers.jobs_ch import get_jobs_ch_scraper
from api.scrapers.swiss_dev_jobs import get_swiss_dev_jobs_scraper

ScraperFactory = Callable[[], BaseJobScraper]

_SCRAPER_FACTORIES: tuple[ScraperFactory, ...] = (
    get_jobs_ch_scraper,
    get_swiss_dev_jobs_scraper,
)


def get_all_scrapers() -> list[BaseJobScraper]:
    """Return every source enabled for live search."""
    return [factory() for factory in _SCRAPER_FACTORIES]


def get_scraper(source_name: str) -> BaseJobScraper | None:
    """Resolve an enabled scraper by its canonical source name."""
    normalized_source = source_name.strip().casefold()
    return next(
        (
            scraper
            for scraper in get_all_scrapers()
            if scraper.source_name.casefold() == normalized_source
        ),
        None,
    )


def get_detail_scraper(source_name: str) -> DetailJobScraper | None:
    """Resolve a source only when it supports on-demand job details."""
    scraper = get_scraper(source_name)
    return scraper if isinstance(scraper, DetailJobScraper) else None
