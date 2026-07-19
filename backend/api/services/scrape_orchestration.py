from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from api.data.models import job_id
from api.scrapers.base import BaseJobScraper
from api.services.job_ingestion import (
    finish_scrape_run,
    get_or_create_source,
    start_scrape_run,
    upsert_jobs,
)


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
        "jobs_created": sum(result["jobs_created"] for result in results),
        "jobs_updated": sum(result["jobs_updated"] for result in results),
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
    run = None
    try:
        get_or_create_source(scraper.source_name, scraper.base_url)
        run = start_scrape_run(scraper.source_name, search_term, location, pages)
        jobs = scraper.scrape(search_term, location, pages)
        created, updated = upsert_jobs(jobs)
        finished = finish_scrape_run(
            run,
            status="completed",
            jobs_found=len(jobs),
            jobs_created=created,
            jobs_updated=updated,
            job_ids=[job_id(job.source_website, str(job.source_url)) for job in jobs],
        )
        return {
            "source_id": finished["source_id"],
            "status": finished["status"],
            "jobs_found": finished["jobs_found"],
            "jobs_created": finished["jobs_created"],
            "jobs_updated": finished["jobs_updated"],
            "error_message": finished.get("error_message"),
            "normalized_jobs": jobs,
        }
    except Exception as exc:
        if run is not None:
            finish_scrape_run(
                run,
                status="failed",
                jobs_found=0,
                jobs_created=0,
                jobs_updated=0,
                error_message=str(exc),
            )
        return {
            "source_id": scraper.source_name.lower(),
            "status": "failed",
            "jobs_found": 0,
            "jobs_created": 0,
            "jobs_updated": 0,
            "error_message": str(exc),
            "normalized_jobs": [],
        }
