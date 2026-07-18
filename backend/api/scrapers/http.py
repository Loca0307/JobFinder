from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Type

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Settings for the http client
@dataclass(frozen=True)
class ScraperHttpConfig:
    user_agent: str
    accept_language: str = "en,de-CH;q=0.9,fr-CH;q=0.8,it-CH;q=0.7"
    connect_timeout: float = 5
    read_timeout: float = 15
    max_retries: int = 3
    backoff_factor: float = 1
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)


class ScraperHttpClient:
    def __init__(self, config: ScraperHttpConfig) -> None:
        self.config = config
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        retry_policy = Retry(
            total=self.config.max_retries,
            connect=self.config.max_retries,
            read=self.config.max_retries,
            status=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
            status_forcelist=self.config.retry_statuses,
            allowed_methods={"GET"},
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_policy)

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": self.config.user_agent,
                "Accept-Language": self.config.accept_language,
            }
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def get(self, url: str) -> requests.Response:
        response = self.session.get(
            url,
            timeout=(self.config.connect_timeout, self.config.read_timeout),
        )
        response.raise_for_status()
        return response

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> ScraperHttpClient:
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
