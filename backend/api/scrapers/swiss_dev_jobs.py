from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from api.data.schemas import NormalizedJob
from api.scrapers.base import BaseJobScraper
from api.scrapers.http import RequestRateLimiter, ScraperHttpClient, ScraperHttpConfig
from api.services.job_attribute_extraction import (
    extract_remote_type,
    extract_required_languages,
    extract_seniority,
)
from api.services.location_normalization import normalize_location
from api.settings.config import get_settings


class SwissDevJobsScraper(BaseJobScraper):
    source_name = "swissdevjobs.ch"
    base_url = "https://swissdevjobs.ch"
    feed_url = f"{base_url}/rss"

    def __init__(self) -> None:
        settings = get_settings()
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

    # Sraping for SwissDevJobs is done via their RSS feed,
    #  which does not support pagination. 
    # Therefore, the `pages` parameter is ignored.
    def scrape(
        self,
        search_term: str | None = None,
        location: str | None = None,
        pages: int = 1,
    ) -> list[NormalizedJob]:
        del pages
        with self._create_http_client() as client:
            response = client.get(self.feed_url)
        return self._parse_feed(response.text, search_term, location)

    # Instead of parsing elements in html page, 
    # RSS sends directly all the data in a XML
    def _parse_feed(
        self,
        xml: str,
        search_term: str | None = None,
        location: str | None = None,
    ) -> list[NormalizedJob]:
        root = ET.fromstring(xml)
        jobs: list[NormalizedJob] = []
        seen_urls: set[str] = set()

        for item in root.findall("./channel/item"):
            job = self._parse_item(item)
            if job is None or str(job.source_url) in seen_urls:
                continue
            if not self._matches(job, item, search_term, location):
                continue
            seen_urls.add(str(job.source_url))
            jobs.append(job)

        return jobs

    def _parse_item(self, item: ET.Element) -> NormalizedJob | None:
        feed_title = self._element_text(item, "title")
        link = self._element_text(item, "link")
        if not feed_title or not link:
            return None

        title, company, title_salary = self._parse_title(feed_title)
        description_html = self._element_text(item, "description") or ""
        soup = BeautifulSoup(description_html, "html.parser")
        requirements = self._section_text(soup, "Requirements")
        responsibilities = self._section_text(soup, "Responsibilities")
        technologies = self._section_text(soup, "Technologies")
        more = self._section_text(soup, "More")
        salary = self._salary_from_description(soup) or title_salary
        description = " ".join(
            part for part in (responsibilities, technologies, more) if part
        ) or soup.get_text(" ", strip=True)
        canonical_url = self._canonical_url(link)

        return NormalizedJob(
            title=title,
            company=company,
            country_code="CH",
            description=description or None,
            requirements=requirements,
            seniority=extract_seniority(title, description),
            remote_type=extract_remote_type(title, description),
            salary=salary,
            required_languages=extract_required_languages(
                title, " ".join(filter(None, (requirements, description)))
            ),
            source_website=self.source_name,
            source_url=canonical_url,
            apply_url=canonical_url,
            posting_date=self._parse_date(self._element_text(item, "pubDate")),
            external_id=canonical_url,
            raw_payload={
                "feed_title": feed_title,
                "technologies": technologies,
                "parser": "rss",
            },
        )

    def _matches(
        self,
        job: NormalizedJob,
        item: ET.Element,
        search_term: str | None,
        location: str | None,
    ) -> bool:
        searchable = " ".join(
            filter(
                None,
                (
                    job.title,
                    job.company,
                    job.description,
                    job.requirements,
                    self._element_text(item, "description"),
                ),
            )
        ).casefold()
        if search_term and search_term.strip().casefold() not in searchable:
            return False
        if location:
            normalized = normalize_location(location).strip()
            if normalized.casefold() not in searchable:
                return False
            job.location = normalized
        return True

    def _parse_title(self, value: str) -> tuple[str, str | None, str | None]:
        salary_match = re.search(r"\s*\[(CHF[^\]]+)\]\s*$", value, re.I)
        salary = salary_match.group(1).strip() if salary_match else None
        without_salary = value[: salary_match.start()].strip() if salary_match else value
        title, separator, company = without_salary.rpartition(" @ ")
        if not separator:
            return without_salary.strip(), None, salary
        return title.strip(), company.strip() or None, salary

    def _section_text(self, soup: BeautifulSoup, name: str) -> str | None:
        heading = soup.find(
            lambda tag: tag.name in {"b", "strong"}
            and tag.get_text(" ", strip=True).rstrip(":").casefold()
            == name.casefold()
        )
        if heading is None:
            return None
        parts: list[str] = []
        for sibling in heading.next_siblings:
            if getattr(sibling, "name", None) in {"b", "strong"}:
                break
            text = (
                sibling.get_text(" ", strip=True)
                if hasattr(sibling, "get_text")
                else str(sibling).strip()
            )
            if text:
                parts.append(text)
        return " ".join(parts) or None

    def _salary_from_description(self, soup: BeautifulSoup) -> str | None:
        match = re.search(
            r"Salary:\s*(.+?)\s+per year(?:\s|$)",
            soup.get_text(" ", strip=True),
            re.I,
        )
        return match.group(1).strip() if match else None

    def _canonical_url(self, value: str) -> str:
        parts = urlsplit(value.strip())
        query = urlencode(
            [
                (key, item)
                for key, item in parse_qsl(parts.query, keep_blank_values=True)
                if not key.casefold().startswith("utm_")
            ]
        )
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))

    def _parse_date(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None

    def _element_text(self, item: ET.Element, name: str) -> str | None:
        element = item.find(name)
        return element.text.strip() if element is not None and element.text else None


@lru_cache(maxsize=1)
def get_swiss_dev_jobs_scraper() -> SwissDevJobsScraper:
    return SwissDevJobsScraper()
