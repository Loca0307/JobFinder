from __future__ import annotations

import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from api.data.models import job_id
from api.data.schemas import NormalizedJob
from api.scrapers.base import BaseJobScraper
from api.services.location_normalization import normalize_location
from api.settings.config import get_settings

logger = logging.getLogger(__name__)


def scrape_sources(
    scrapers: list[BaseJobScraper],
    search_term: str | None,
    location: str | None,
    pages_by_source: dict[str, int] | None = None,
) -> dict[str, Any]:
    pages_by_source = pages_by_source or {}
    source_workers = min(get_settings().scraper_source_max_workers, len(scrapers))
    with ThreadPoolExecutor(max_workers=source_workers) as executor:
        tasks = {
            executor.submit(
                _scrape_source,
                scraper,
                search_term,
                location,
                pages_by_source.get(scraper.source_name, scraper.default_pages),
            ): scraper.source_name
            for scraper in scrapers
        }
        results = [task.result() for task in as_completed(tasks)]

    results.sort(key=lambda result: result["source_id"])
    successful = [result for result in results if result["status"] == "completed"]
    jobs = deduplicate_jobs(
        [job for result in successful for job in result["normalized_jobs"]]
    )
    for result in results:
        result.pop("normalized_jobs")
    status = "completed" if len(successful) == len(results) else "partial"
    if not successful:
        status = "failed"

    return {
        "status": status,
        "jobs_found": len(jobs),
        "jobs": [
            {
                "id": job_id(job.source_website, str(job.source_url)),
                **job.model_dump(mode="json"),
            }
            for job in jobs
        ],
        "sources": results,
    }


def deduplicate_jobs(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    """Deduplicate the final multi-source list by normalized vacancy identity."""
    unique_jobs: list[NormalizedJob] = []
    seen_vacancies: set[tuple[str, str, str]] = set()

    for job in jobs:
        fingerprint = _vacancy_fingerprint(job)
        if fingerprint is not None and fingerprint in seen_vacancies:
            logger.info(
                "Dropped duplicate vacancy from %s: %s at %s",
                job.source_website,
                job.title,
                job.company,
            )
            continue
        if fingerprint is not None:
            seen_vacancies.add(fingerprint)
        unique_jobs.append(job)

    return unique_jobs


def _vacancy_fingerprint(job: NormalizedJob) -> tuple[str, str, str] | None:
    """Return a conservative cross-board identity for a normalized job."""
    title = _identity_text(job.title)
    company = _identity_text(job.company)
    location = _identity_text(normalize_location(job.location))
    if not title or not company or not location:
        return None
    return title, company, location


def _identity_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"\w+", normalized))


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
