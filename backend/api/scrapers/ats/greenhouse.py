from __future__ import annotations

import html
import json
from collections.abc import Callable
from typing import Any

from bs4 import BeautifulSoup

from api.data.schemas import NormalizedJob
from api.scrapers.ats.search import matches_search
from api.scrapers.ats.targets import GreenhouseTarget
from api.scrapers.base import BaseJobScraper, ScrapeError
from api.scrapers.http import RequestRateLimiter, ScraperHttpClient, ScraperHttpConfig
from api.services.job_attribute_extraction import (
    extract_remote_type,
    extract_required_languages,
    extract_seniority,
)
from api.services.swiss_territory import country_code_from_evidence
from api.settings.config import get_settings


class GreenhouseScraper(BaseJobScraper):
    """Search one company's public Greenhouse job board."""

    def __init__(
        self,
        target: GreenhouseTarget,
        *,
        client_factory: Callable[[], ScraperHttpClient] | None = None,
    ) -> None:
        self.target = target
        self.source_name = target.source_name
        self.base_url = str(target.careers_url)
        settings = get_settings()
        self.http_config = ScraperHttpConfig(
            user_agent=settings.scraper_user_agent,
            connect_timeout=settings.scraper_connect_timeout_seconds,
            read_timeout=settings.scraper_read_timeout_seconds,
            max_retries=settings.scraper_max_retries,
            backoff_factor=settings.scraper_retry_backoff_factor,
        )
        self.rate_limiter = RequestRateLimiter(settings.scraper_requests_per_second)
        self._client_factory = client_factory or self._create_http_client

    @property
    def jobs_url(self) -> str:
        return (
            "https://boards-api.greenhouse.io/v1/boards/"
            f"{self.target.board_token}/jobs?content=true"
        )

    def _create_http_client(self) -> ScraperHttpClient:
        return ScraperHttpClient(self.http_config, self.rate_limiter)

    def scrape(
        self,
        search_term: str | None = None,
        location: str | None = None,
        pages: int | None = None,
    ) -> list[NormalizedJob]:
        del pages
        with self._client_factory() as client:
            response = client.get(self.jobs_url)
        return [
            job
            for job in self._parse_jobs(response.text)
            if matches_search(job, search_term, location)
        ]

    def _parse_jobs(self, body: str) -> list[NormalizedJob]:
        try:
            jobs = json.loads(body)["jobs"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ScrapeError("Greenhouse jobs payload is malformed") from exc
        if not isinstance(jobs, list):
            raise ScrapeError("Greenhouse jobs must be a list")

        normalized_jobs: list[NormalizedJob] = []
        seen_ids: set[str] = set()
        usable_candidates = 0
        for item in jobs:
            # Greenhouse uses a null internal ID for general-interest posts,
            # which are not concrete vacancies.
            if (
                isinstance(item, dict)
                and "internal_job_id" in item
                and item["internal_job_id"] is None
            ):
                continue
            usable_candidates += 1
            job = self._normalize(item) if isinstance(item, dict) else None
            if job is None or job.external_id in seen_ids:
                continue
            seen_ids.add(job.external_id or "")
            normalized_jobs.append(job)

        if usable_candidates and not normalized_jobs:
            raise ScrapeError("Greenhouse payload has no usable jobs")
        return normalized_jobs

    def _normalize(self, item: dict[str, Any]) -> NormalizedJob | None:
        source_id = item.get("id")
        title = _text(item.get("title"))
        source_url = _text(item.get("absolute_url"))
        if source_id in (None, "") or not title or not source_url:
            return None

        location_data = item.get("location")
        location = (
            _text(location_data.get("name"))
            if isinstance(location_data, dict)
            else None
        )
        content = _text(item.get("content"))
        description = (
            BeautifulSoup(html.unescape(content), "html.parser").get_text(
                "\n", strip=True
            )
            if content
            else None
        )
        try:
            return NormalizedJob(
                title=title,
                company=self.target.company_name,
                location=location,
                country_code=country_code_from_evidence(location),
                description=description,
                seniority=extract_seniority(title, description),
                remote_type=extract_remote_type(title, description),
                required_languages=extract_required_languages(title, description),
                source_website=self.source_name,
                source_url=source_url,
                apply_url=source_url,
                external_id=str(source_id),
                raw_payload={
                    "parser": "greenhouse_api",
                    "target_id": self.target.id,
                },
            )
        except ValueError:
            return None


def _text(value: object) -> str | None:
    return str(value).strip() if value not in (None, "") else None
