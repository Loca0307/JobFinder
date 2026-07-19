from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.data.schemas import (
    JobInteractionRead,
    JobInteractionWrite,
    JobScrapeRequest,
    MultiSourceScrapeResult,
)
from api.scrapers.jobs_ch import get_jobs_ch_scraper
from api.scrapers.swiss_dev_jobs import get_swiss_dev_jobs_scraper
from api.services.scrape_orchestration import scrape_sources
from api.services.job_interactions import (
    list_job_interactions,
    save_job_interaction,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])
JOBS_CH_PAGES = 5
SWISS_DEV_JOBS_PAGES = 5


@router.post("/scrape", response_model=MultiSourceScrapeResult)
def scrape_all_sources(request: JobScrapeRequest) -> MultiSourceScrapeResult:
    result = scrape_sources(
        [get_jobs_ch_scraper(), get_swiss_dev_jobs_scraper()],
        request.search_term,
        request.location,
        {
            "jobs.ch": JOBS_CH_PAGES,
            "swissdevjobs.ch": SWISS_DEV_JOBS_PAGES,
        },
    )
    if result["status"] == "failed":
        raise HTTPException(status_code=502, detail=result)
    return result


@router.get("/interactions", response_model=list[JobInteractionRead])
def get_interactions() -> list[JobInteractionRead]:
    return list_job_interactions()


@router.put(
    "/interactions/{job_id:path}",
    response_model=JobInteractionRead | None,
)
def put_interaction(
    job_id: str,
    interaction: JobInteractionWrite,
) -> JobInteractionRead | None:
    if interaction.job.id != job_id:
        raise HTTPException(status_code=400, detail="Job ID does not match URL")
    return save_job_interaction(job_id, interaction)
