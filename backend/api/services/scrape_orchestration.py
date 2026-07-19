from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from api.data.models import job_id
from api.scrapers.base import BaseJobScraper

logger = logging.getLogger(__name__)


def scrape_sources(
    scrapers: list[BaseJobScraper],
    search_term: str | None,
    location: str | None,
    pages_by_source: dict[str, int],
) -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=len(scrapers)) as executor:
        tasks = {
            executor.submit(
                _scrape_source,
                scraper,
                search_term,
                location,
                pages_by_source.get(scraper.source_name, 1),
            ): scraper.source_name
            for scraper in scrapers
        }
        results = [task.result() for task in as_completed(tasks)]

    results.sort(key=lambda result: result["source_id"])
    successful = [result for result in results if result["status"] == "completed"]
    jobs = [job for result in successful for job in result["normalized_jobs"]]
    for result in results:
        result.pop("normalized_jobs")
    status = "completed" if len(successful) == len(results) else "partial"
    if not successful:
        status = "failed"

    return {
        "status": status,
        "jobs_found": sum(result["jobs_found"] for result in results),
        "jobs": [
            {
                "id": job_id(job.source_website, str(job.source_url)),
                **job.model_dump(mode="json"),
            }
            for job in jobs
        ],
        "sources": results,
    }


def _scrape_source(
    scraper: BaseJobScraper,
    search_term: str | None,
    location: str | None,
    pages: int,
) -> dict[str, Any]:
    try:
        jobs = scraper.scrape(search_term, location, pages)
        logger.info(
            "Live scrape completed for %s with %s jobs",
            scraper.source_name,
            len(jobs),
        )
        return {
            "source_id": scraper.source_name.lower(),
            "status": "completed",
            "jobs_found": len(jobs),
            "error_message": None,
            "normalized_jobs": jobs,
        }
    except Exception as exc:
        logger.exception("Live scrape failed for %s", scraper.source_name)
        return {
            "source_id": scraper.source_name.lower(),
            "status": "failed",
            "jobs_found": 0,
            "error_message": str(exc),
            "normalized_jobs": [],
        }
