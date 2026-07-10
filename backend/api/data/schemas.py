from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


# Job instance structure saved in dynamo db 
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
    company: Optional[str]
    location: Optional[str]
    description: Optional[str]
    requirements: Optional[str]
    seniority: Optional[str]
    employment_type: Optional[str]
    remote_type: Optional[str]
    salary: Optional[str]
    required_languages: List[str]
    source_website: str
    source_url: str
    apply_url: Optional[str]
    posting_date: Optional[datetime]
    scrape_timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


# Parameters for requests sent by agent to scrape jobs
class JobScrapeRequest(BaseModel):
    search_term: Optional[str] = Field(default=None, max_length=255)
    location: Optional[str] = Field(default=None, max_length=255)
    pages: int = Field(default=1, ge=1, le=5)


# Meta data received from scraping requests
class ScrapeRunRead(BaseModel):
    id: str
    status: str
    source_id: str
    search_term: Optional[str]
    location: Optional[str]
    pages_requested: int
    jobs_found: int
    jobs_created: int
    jobs_updated: int
    error_message: Optional[str]
    started_at: datetime
    finished_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
