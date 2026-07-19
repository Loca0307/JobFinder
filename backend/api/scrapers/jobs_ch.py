from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from functools import lru_cache
from typing import Any
import requests

from api.settings.config import get_settings
from api.data.schemas import NormalizedJob
from api.scrapers.base import PaginatedJobScraper
from api.scrapers.http import RequestRateLimiter, ScraperHttpClient, ScraperHttpConfig
from api.services.job_attribute_extraction import (
    extract_remote_type,
    extract_required_languages,
    extract_seniority,
    normalize_structured_remote_type,
)
from api.services.location_normalization import normalize_location

logger = logging.getLogger(__name__)


# Job scraper, sub class of BaseJobScraper, useds to scrape jobs.ch website
class JobsChScraper(PaginatedJobScraper):
    source_name = "jobs.ch"
    base_url = "https://www.jobs.ch"

    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(max_workers=settings.scraper_max_workers)
        self.http_config = ScraperHttpConfig(
            user_agent=settings.scraper_user_agent,
            connect_timeout=settings.scraper_connect_timeout_seconds,
            read_timeout=settings.scraper_read_timeout_seconds,
            max_retries=settings.scraper_max_retries,
            backoff_factor=settings.scraper_retry_backoff_factor,
        )
        self.rate_limiter = RequestRateLimiter(settings.scraper_requests_per_second)

    def _create_http_client(self) -> ScraperHttpClient:
        return ScraperHttpClient(self.http_config, self.rate_limiter)

    def _scrape_page(
        self,
        search_term: str | None,
        location: str | None,
        page: int,
    ) -> tuple[int, list[NormalizedJob]]:
        listing_url = self._build_listing_url(search_term, location, page)

        with self._create_http_client() as client:
            response = client.get(listing_url)
            jobs = self._extract_listing_jobs(response.text)

        return page, jobs

    # Builds the specific url to scrape for url and page
    def _build_listing_url(
        self, search_term: str | None, location: str | None, page: int
    ) -> str:
        params: list[str] = []
        if search_term:
            params.append(f"term={requests.utils.quote(search_term)}")
        if location:
            normalized_location = normalize_location(location)
            params.append(f"location={requests.utils.quote(normalized_location)}")
        if page > 1:
            params.append(f"page={page}")
        query = "&".join(params)
        return f"{self.base_url}/en/vacancies/{'?' + query if query else ''}"

    def _extract_listing_jobs(self, html: str) -> list[NormalizedJob]:
        marker = re.search(r"__INIT__\s*=\s*", html)
        if marker is None:
            return []

        try:
            state, _ = json.JSONDecoder().raw_decode(html, marker.end())
            results = state["vacancy"]["results"]["main"]["results"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return []

        jobs: list[NormalizedJob] = []
        for summary in results:
            external_id = summary.get("id")
            title = summary.get("title")
            if not external_id or not title:
                continue

            url = f"{self.base_url}/en/vacancies/detail/{external_id}/"
            company = summary.get("company") or {}
            jobs.append(
                NormalizedJob(
                    title=title,
                    company=company.get("name") if isinstance(company, dict) else None,
                    location=summary.get("place"),
                    source_website=self.source_name,
                    source_url=url,
                    apply_url=url,
                    posting_date=self._parse_datetime(summary.get("publicationDate")),
                    external_id=external_id,
                    raw_payload={"parser": "listing_summary"},
                    details_loaded=False,
                )
            )
        return jobs

    def scrape_detail(self, external_id: str) -> NormalizedJob | None:
        if re.fullmatch(r"[A-Za-z0-9-]+", external_id) is None:
            raise ValueError("Invalid jobs.ch job ID")
        url = f"{self.base_url}/en/vacancies/detail/{external_id}/"
        with self._create_http_client() as client:
            return self._scrape_detail(url, client)

    # Extract a single normalizesJob from the url
    def _scrape_detail(
        self, url: str, client: ScraperHttpClient
    ) -> NormalizedJob | None:
        response = client.get(url)
        soup = _beautiful_soup(response.text)
        payload = self._extract_job_posting_json(soup)

        if payload:
            return self._from_json_ld(payload, url)

        title = self._text_or_none(soup.find(["h1", "title"]))
        if not title:
            return None

        description_node = soup.find(attrs={"data-cy": re.compile("description", re.I)})
        description = self._text_or_none(description_node) or self._text_or_none(
            soup.find("main")
        )

        return NormalizedJob(
            title=title,
            company=None,
            location=None,
            description=description,
            seniority=extract_seniority(title, description),
            remote_type=extract_remote_type(title, description),
            required_languages=extract_required_languages(title, description),
            source_website=self.source_name,
            source_url=url,
            apply_url=url,
            raw_payload={"parser": "html_fallback"},
        )

    def _extract_job_posting_json(self, soup: Any) -> dict | None:
        for script in soup.find_all("script", type="application/ld+json"):
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue

            candidates = data if isinstance(data, list) else [data]
            for item in candidates:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    return item
        return None

    def _from_json_ld(self, payload: dict, url: str) -> NormalizedJob:
        organization = payload.get("hiringOrganization") or {}
        location = payload.get("jobLocation")
        salary = payload.get("baseSalary")
        title = payload.get("title") or "Untitled job"
        description = self._strip_html(payload.get("description"))

        return NormalizedJob(
            title=title,
            company=self._organization_name(organization),
            location=self._location_name(location),
            description=description,
            requirements=self._strip_html(
                payload.get("qualifications") or payload.get("skills")
            ),
            seniority=extract_seniority(title, description),
            employment_type=self._join_value(payload.get("employmentType")),
            remote_type=normalize_structured_remote_type(
                payload.get("jobLocationType")
            )
            or extract_remote_type(title, description),
            salary=self._salary_text(salary),
            required_languages=extract_required_languages(title, description),
            source_website=self.source_name,
            source_url=url,
            apply_url=payload.get("url") or url,
            posting_date=self._parse_datetime(
                payload.get("datePosted") or payload.get("validThrough")
            ),
            external_id=payload.get("identifier", {}).get("value")
            if isinstance(payload.get("identifier"), dict)
            else None,
            raw_payload=payload,
        )

    def _organization_name(self, organization: dict | str) -> str | None:
        if isinstance(organization, dict):
            return organization.get("name")
        if isinstance(organization, str):
            return organization
        return None

    def _location_name(self, location: dict | list | str | None) -> str | None:
        if isinstance(location, list):
            return "; ".join(
                filter(None, [self._location_name(item) for item in location])
            )
        if isinstance(location, str):
            return location
        if not isinstance(location, dict):
            return None

        address = location.get("address")
        if isinstance(address, dict):
            parts = [
                address.get("addressLocality"),
                address.get("addressRegion"),
                address.get("addressCountry"),
            ]
            return ", ".join(part for part in parts if part)
        return None

    def _salary_text(self, salary: dict | str | None) -> str | None:
        if isinstance(salary, str):
            return salary
        if not isinstance(salary, dict):
            return None
        value = salary.get("value")
        currency = salary.get("currency")
        if isinstance(value, dict):
            min_value = value.get("minValue")
            max_value = value.get("maxValue")
            unit = value.get("unitText")
            range_text = " - ".join(str(item) for item in [min_value, max_value] if item)
            return " ".join(str(item) for item in [currency, range_text, unit] if item)
        return None

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _join_value(self, value: list | str | None) -> str | None:
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        if value is None:
            return None
        return str(value)

    def _strip_html(self, value: str | list | None) -> str | None:
        if not value:
            return None
        if isinstance(value, list):
            value = " ".join(str(item) for item in value if item)
        return _beautiful_soup(value).get_text(" ", strip=True)

    def _text_or_none(self, node) -> str | None:
        if node is None:
            return None
        text = node.get_text(" ", strip=True)
        return text or None


def _beautiful_soup(html: str):
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "html.parser")


@lru_cache(maxsize=1)
def get_jobs_ch_scraper() -> JobsChScraper:
    """Return the single jobs.ch scraper used by this backend process."""
    return JobsChScraper()
