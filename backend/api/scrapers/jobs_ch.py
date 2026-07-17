from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import requests

from api.settings.config import get_settings
from api.data.schemas import NormalizedJob
from api.scrapers.base import BaseJobScraper
from api.services.job_attribute_extraction import (
    extract_remote_type,
    extract_required_languages,
    extract_seniority,
    normalize_structured_remote_type,
)
from api.services.location_normalization import normalize_location

logger = logging.getLogger(__name__)


# Job scraper, sub class of BaseJobScraper, useds to scrape jobs.ch website
class JobsChScraper(BaseJobScraper):
    source_name = "jobs.ch"
    base_url = "https://www.jobs.ch"

    def __init__(self) -> None:
        settings = get_settings() # Loads setting configuration for specific scraper
        self.session = requests.Session() # Creates session wiht the website to use efficiently more requests per session
        self.session.headers.update(
            {
                "User-Agent": settings.scraper_user_agent,
                "Accept-Language": "en,de-CH;q=0.9,fr-CH;q=0.8,it-CH;q=0.7",
            }
        )
        self.timeout = settings.scraper_timeout_seconds

    def scrape(
        self,
        search_term: str | None = None,
        location: str | None = None,
        pages: int = 1,
    ) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        seen_urls: set[str] = set()

        for page in range(1, pages + 1):
            listing_url = self._build_listing_url(search_term, location, page)
            try:
                # Sends the actual request for the data
                response = self.session.get(listing_url, timeout=self.timeout)
                response.raise_for_status()
            except requests.RequestException as exc:
                logger.warning("jobs.ch listing request failed: %s", exc)
                continue

            detail_urls = self._extract_detail_urls(response.text)
            
            for detail_url in detail_urls: # Checks for url duplication
                if detail_url in seen_urls:
                    continue
                seen_urls.add(detail_url)

                try:
                    job = self._scrape_detail(detail_url)
                except Exception:
                    logger.exception("jobs.ch detail scrape failed for %s", detail_url)
                    continue

                if job is not None:
                    jobs.append(job)

        return jobs

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

    # Extract urls for job listing pages
    def _extract_detail_urls(self, html: str) -> list[str]:
        soup = _beautiful_soup(html)
        urls: list[str] = []
        patterns = (
            "/en/vacancies/detail/",
            "/de/stellenangebote/detail/",
            "/fr/offres-emplois/detail/",
            "/it/offerte-lavoro/detail/",
        )

        for anchor in soup.find_all("a", href=True):
            href = str(anchor["href"])
            if any(pattern in href for pattern in patterns):
                clean_url = urljoin(self.base_url, href.split("?")[0])
                if clean_url not in urls:
                    urls.append(clean_url)

        return urls

    # Extract a single normalizesJob from the url
    def _scrape_detail(self, url: str) -> NormalizedJob | None:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
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
