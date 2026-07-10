from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from api.data.schemas import JobRead, JobScrapeRequest, ScrapeRunRead
from api.scrapers.jobs_ch import JobsChScraper
from api.services.job_ingestion import (
    finish_scrape_run,
    get_or_create_source,
    list_jobs as list_stored_jobs,
    start_scrape_run,
    upsert_jobs,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])

#@router.get("health")
#def health(x):
    


@router.get("", response_model=List[JobRead])
def list_jobs(limit: int = 50) -> List[dict]:
    limit = max(1, min(limit, 200))
    return list_stored_jobs(limit=limit)


@router.post("/scrape/jobs-ch", response_model=ScrapeRunRead)
def scrape_jobs_ch(
    request: JobScrapeRequest,
) -> ScrapeRunRead:
    scraper = JobsChScraper()
    get_or_create_source(scraper.source_name, scraper.base_url)
    run = start_scrape_run(
        source_name=scraper.source_name,
        search_term=request.search_term,
        location=request.location,
        pages=request.pages,
    )

    try:
        normalized_jobs = scraper.scrape(
            search_term=request.search_term,
            location=request.location,
            pages=request.pages,
        )
        created, updated = upsert_jobs(normalized_jobs)
        return finish_scrape_run(
            run,
            status="completed",
            jobs_found=len(normalized_jobs),
            jobs_created=created,
            jobs_updated=updated,
        )
    except Exception as exc:
        finish_scrape_run(
            run,
            status="failed",
            jobs_found=0,
            jobs_created=0,
            jobs_updated=0,
            error_message=str(exc),
        )
        raise HTTPException(status_code=502, detail="jobs.ch scrape failed") from exc
