from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from api.data.schemas import NormalizedJob
from api.scrapers.ats.search import matches_search
from api.scrapers.ats.targets import LeverTarget
from api.scrapers.base import DEFAULT_PAGE_COUNT, BaseJobScraper, ScrapeError
from api.scrapers.http import RequestRateLimiter, ScraperHttpClient, ScraperHttpConfig
from api.services.job_attribute_extraction import (
    extract_remote_type,
    extract_required_languages,
    extract_seniority,
)
from api.services.swiss_territory import country_code_from_evidence
from api.settings.config import get_settings

PAGE_SIZE = 100


class LeverScraper(BaseJobScraper):
    """Search one company's public Lever postings with bounded pagination."""

    default_pages = DEFAULT_PAGE_COUNT

    def __init__(
        self,
        target: LeverTarget,
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

    def _create_http_client(self) -> ScraperHttpClient:
        return ScraperHttpClient(self.http_config, self.rate_limiter)

    def _page_url(self, page: int) -> str:
        host = "api.eu.lever.co" if self.target.region == "eu" else "api.lever.co"
        query = urlencode(
            {"mode": "json", "skip": page * PAGE_SIZE, "limit": PAGE_SIZE}
        )
        return f"https://{host}/v0/postings/{self.target.site}?{query}"

    def scrape(
        self,
        search_term: str | None = None,
        location: str | None = None,
        pages: int | None = None,
    ) -> list[NormalizedJob]:
        max_pages = self.default_pages if pages is None else pages
        if max_pages < 1:
            return []

        jobs: list[NormalizedJob] = []
        seen_ids: set[str] = set()
        page_signatures: set[tuple[str, ...]] = set()
        with self._client_factory() as client:
            # Probe once beyond the cap so an exactly-full last page is not
            # mistaken for a truncated board.
            for page in range(max_pages + 1):
                items = self._parse_page(client.get(self._page_url(page)).text)
                if not items:
                    return jobs
                if page == max_pages:
                    raise ScrapeError(
                        "Lever reached its page limit before the final page"
                    )

                signature = tuple(
                    str(item.get("id")) for item in items if item.get("id")
                )
                if signature in page_signatures:
                    raise ScrapeError("Lever returned a repeated page")
                page_signatures.add(signature)

                normalized_page = [
                    job for item in items if (job := self._normalize(item)) is not None
                ]
                if items and not normalized_page:
                    raise ScrapeError("Lever payload has no usable jobs")
                for job in normalized_page:
                    if job.external_id in seen_ids:
                        continue
                    seen_ids.add(job.external_id or "")
                    if matches_search(job, search_term, location):
                        jobs.append(job)

                if len(items) < PAGE_SIZE:
                    return jobs

        return jobs

    def _parse_page(self, body: str) -> list[dict[str, Any]]:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ScrapeError("Lever jobs payload is malformed") from exc
        if not isinstance(payload, list):
            raise ScrapeError("Lever jobs must be a list")
        if payload and not any(isinstance(item, dict) for item in payload):
            raise ScrapeError("Lever jobs contain no objects")
        return [item for item in payload if isinstance(item, dict)]

    def _normalize(self, item: dict[str, Any]) -> NormalizedJob | None:
        source_id = item.get("id")
        title = _text(item.get("text"))
        source_url = _text(item.get("hostedUrl"))
        if source_id in (None, "") or not title or not source_url:
            return None

        categories = item.get("categories")
        categories = categories if isinstance(categories, dict) else {}
        location = _locations(categories.get("allLocations")) or _text(
            categories.get("location")
        )
        introduction = _text(item.get("descriptionPlain")) or _html_text(
            item.get("description")
        )
        lists_text = _lists_text(item.get("lists"))
        description = "\n\n".join(filter(None, (introduction, lists_text))) or None
        requirements = _requirements(item.get("lists"))
        remote_type = _workplace_type(item.get("workplaceType")) or (
            extract_remote_type(title, description)
        )
        try:
            return NormalizedJob(
                title=title,
                company=self.target.company_name,
                location=location,
                country_code=country_code_from_evidence(
                    location,
                    structured_country=item.get("country"),
                ),
                description=description,
                requirements=requirements,
                seniority=extract_seniority(title, description),
                employment_type=_text(categories.get("commitment")),
                remote_type=remote_type,
                salary=_salary(item),
                required_languages=extract_required_languages(
                    title, " ".join(filter(None, (description, requirements)))
                ),
                source_website=self.source_name,
                source_url=source_url,
                apply_url=_text(item.get("applyUrl")) or source_url,
                external_id=str(source_id),
                raw_payload={
                    "parser": "lever_api",
                    "target_id": self.target.id,
                },
            )
        except ValueError:
            return None


def _text(value: object) -> str | None:
    return str(value).strip() if value not in (None, "") else None


def _html_text(value: object) -> str | None:
    text = _text(value)
    if not text:
        return None
    return BeautifulSoup(text, "html.parser").get_text("\n", strip=True)


def _locations(value: object) -> str | None:
    if not isinstance(value, list):
        return None
    unique = list(dict.fromkeys(text for item in value if (text := _text(item))))
    return ", ".join(unique) or None


def _requirements(value: object) -> str | None:
    if not isinstance(value, list):
        return None
    requirements: list[str] = []
    for section in value:
        if not isinstance(section, dict):
            continue
        label = _text(section.get("text"))
        content = _html_text(section.get("content"))
        if (
            label
            and content
            and any(
                marker in label.casefold()
                for marker in ("requirement", "qualification", "must have")
            )
        ):
            requirements.append(content)
    return "\n\n".join(requirements) or None


def _lists_text(value: object) -> str | None:
    if not isinstance(value, list):
        return None
    sections: list[str] = []
    for section in value:
        if not isinstance(section, dict):
            continue
        label = _text(section.get("text"))
        content = _html_text(section.get("content"))
        if content:
            sections.append("\n\n".join(filter(None, (label, content))))
    return "\n\n".join(sections) or None


def _workplace_type(value: object) -> str | None:
    workplace = _text(value)
    return {
        "remote": "remote",
        "hybrid": "hybrid",
        "on-site": "on_site",
    }.get(workplace or "")


def _salary(item: dict[str, Any]) -> str | None:
    description = _text(item.get("salaryDescriptionPlain"))
    if description:
        return description
    salary = item.get("salaryRange")
    if not isinstance(salary, dict):
        return None
    minimum = salary.get("min")
    maximum = salary.get("max")
    if not isinstance(minimum, (int, float)) and not isinstance(maximum, (int, float)):
        return None
    if minimum is not None and maximum is not None:
        amount = f"{minimum:g}\u2013{maximum:g}"
    else:
        amount = f"{minimum if minimum is not None else maximum:g}"
    currency = f"{salary['currency']} " if salary.get("currency") else ""
    interval = f" per {salary['interval']}" if salary.get("interval") else ""
    return f"{currency}{amount}{interval}"
