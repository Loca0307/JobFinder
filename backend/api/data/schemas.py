from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, HttpUrl


# Normalized job returned by every scraper
class NormalizedJob(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    seniority: Optional[str] = None
    employment_type: Optional[str] = None
    remote_type: Optional[str] = None
    salary: Optional[str] = None
    required_languages: List[str] = Field(default_factory=list)
    source_website: str
    source_url: HttpUrl
    apply_url: Optional[HttpUrl] = None
    posting_date: Optional[datetime] = None
    scrape_timestamp: datetime = Field(default_factory=datetime.utcnow)
    external_id: Optional[str] = None
    raw_payload: Optional[dict[str, Any]] = None


# Structure for API responses received by agents
class JobRead(BaseModel):
    id: str
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    seniority: Optional[str] = None
    employment_type: Optional[str] = None
    remote_type: Optional[str] = None
    salary: Optional[str] = None
    required_languages: List[str] = Field(default_factory=list)
    source_website: Optional[str] = None
    source_url: Optional[str] = None
    apply_url: Optional[str] = None
    posting_date: Optional[datetime] = None
    scrape_timestamp: Optional[datetime] = None
    external_id: Optional[str] = None
    raw_payload: Optional[dict[str, Any]] = None

# Parameters for requests sent by agent to scrape jobs
class JobScrapeRequest(BaseModel):
    search_term: Optional[str] = Field(default=None, max_length=255)
    location: Optional[str] = Field(default=None, max_length=255)


class ScrapeSummary(BaseModel):
    status: str
    jobs_found: int


class SourceScrapeResult(ScrapeSummary):
    source_id: str
    error_message: Optional[str] = None


class MultiSourceScrapeResult(ScrapeSummary):
    jobs: List[JobRead] = Field(default_factory=list)
    sources: List[SourceScrapeResult] = Field(default_factory=list)


class JobInteractionWrite(BaseModel):
    job: JobRead
    starred: bool = False
    applied: bool = False


class JobInteractionRead(JobInteractionWrite):
    applied_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
