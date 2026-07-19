from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.data.schemas import (
    JobInteractionRead,
    JobInteractionWrite,
    JobRead,
    JobScrapeRequest,
    MultiSourceScrapeResult,
)
from api.data.models import job_id
from api.scrapers.registry import get_all_scrapers, get_detail_scraper, get_scraper
from api.services.scrape_orchestration import scrape_sources
from api.services.job_interactions import (
    list_job_interactions,
    save_job_interaction,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/scrape", response_model=MultiSourceScrapeResult)
def scrape_all_sources(request: JobScrapeRequest) -> MultiSourceScrapeResult:
    result = scrape_sources(
        get_all_scrapers(),
        request.search_term,
        request.location,
    )
    if result["status"] == "failed":
        raise HTTPException(status_code=502, detail=result)
    return result


@router.get("/details/{source_id}/{external_id}", response_model=JobRead)
def get_job_detail(source_id: str, external_id: str) -> dict:
    if get_scraper(source_id) is None:
        raise HTTPException(status_code=404, detail="Unknown job source")

    scraper = get_detail_scraper(source_id)
    if scraper is None:
        raise HTTPException(
            status_code=404,
            detail="Job source does not support detail loading",
        )

    try:
        job = scraper.scrape_detail(external_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Job detail request failed") from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job_id(job.source_website, str(job.source_url)),
        **job.model_dump(mode="json"),
    }


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
