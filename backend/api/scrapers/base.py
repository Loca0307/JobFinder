from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed

from api.data.schemas import NormalizedJob

logger = logging.getLogger(__name__)


# Abstract class used to implement scrapers
class BaseJobScraper(ABC):
    source_name: str
    base_url: str

    @abstractmethod
    def scrape(
        self,
        search_term: str | None = None,
        location: str | None = None,
        pages: int = 5,
    ) -> list[NormalizedJob]:
        """Return normalized jobs without persisting them."""


class PaginatedJobScraper(BaseJobScraper):
    """Shared concurrent coordinator for page-based job sources."""

    def __init__(self, max_workers: int = 5) -> None:
        self.max_workers = max_workers

    def scrape(
        self,
        search_term: str | None = None,
        location: str | None = None,
        pages: int = 5,
    ) -> list[NormalizedJob]:
        """Scrape pages concurrently and merge their normalized jobs."""
        if pages < 1:
            return []

        page_results: dict[int, list[NormalizedJob]] = {}

        with ThreadPoolExecutor(max_workers=min(self.max_workers, pages)) as executor:
            page_tasks = {}

            for page in range(1, pages + 1):
                task = executor.submit(
                    self._scrape_page,
                    search_term,
                    location,
                    page,
                )
                page_tasks[task] = page

            for completed_task in as_completed(page_tasks):
                page = page_tasks[completed_task]
                try:
                    result_page, jobs = completed_task.result()
                    page_results[result_page] = jobs
                except Exception:
                    logger.exception(
                        "Unexpected %s page worker failure for page %s",
                        self.source_name,
                        page,
                    )
                    page_results[page] = []

        return self._merge_page_results(page_results)

    @abstractmethod
    def _scrape_page(
        self,
        search_term: str | None,
        location: str | None,
        page: int,
    ) -> tuple[int, list[NormalizedJob]]:
        """Scrape one listing page and its job details."""

    def _merge_page_results(
        self, page_results: dict[int, list[NormalizedJob]]
    ) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        seen_urls: set[str] = set()

        for page in sorted(page_results):
            for job in page_results[page]:
                source_url = str(job.source_url)
                if source_url in seen_urls:
                    continue
                seen_urls.add(source_url)
                jobs.append(job)

        return jobs
