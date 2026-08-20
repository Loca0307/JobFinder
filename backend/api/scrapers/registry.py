from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from api.scrapers.ats.greenhouse import GreenhouseScraper
from api.scrapers.ats.lever import LeverScraper
from api.scrapers.ats.targets import (
    GreenhouseTarget,
    LeverTarget,
    load_company_target_catalog,
)
from api.scrapers.base import BaseJobScraper, DetailJobScraper
from api.scrapers.jobs_ch import get_jobs_ch_scraper
from api.scrapers.jobup_ch import get_jobup_ch_scraper
from api.scrapers.swiss_dev_jobs import get_swiss_dev_jobs_scraper

ScraperFactory = Callable[[], BaseJobScraper]
COMPANY_TARGETS_FILE = Path(__file__).with_name("company_targets.json")

_SCRAPER_FACTORIES: tuple[ScraperFactory, ...] = (
    get_jobs_ch_scraper,
    get_jobup_ch_scraper,
    get_swiss_dev_jobs_scraper,
)


def get_all_scrapers() -> list[BaseJobScraper]:
    """Return every source enabled for live search."""
    return [factory() for factory in _SCRAPER_FACTORIES] + list(get_company_scrapers())


@lru_cache(maxsize=1)
def get_company_scrapers() -> tuple[BaseJobScraper, ...]:
    """Expand the validated company catalog into independent live sources."""
    catalog = load_company_target_catalog(COMPANY_TARGETS_FILE)
    scrapers: list[BaseJobScraper] = []
    for target in catalog.targets:
        if isinstance(target, GreenhouseTarget):
            scrapers.append(GreenhouseScraper(target))
        elif isinstance(target, LeverTarget):
            scrapers.append(LeverScraper(target))
    return tuple(scrapers)


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
