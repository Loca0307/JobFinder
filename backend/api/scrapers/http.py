from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic, sleep
from types import TracebackType
from typing import Callable, Type

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


class RequestRateLimiter:
    """Space request starts across all clients that share this instance."""

    def __init__(
        self,
        requests_per_second: float,
        clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self.interval = 0 if requests_per_second <= 0 else 1 / requests_per_second
        self._clock = clock
        self._sleep = sleeper
        self._next_request_at = 0.0
        self._lock = Lock()

    def wait(self) -> None:
        if self.interval == 0:
            return

        with self._lock:
            now = self._clock()
            delay = max(0.0, self._next_request_at - now)
            self._next_request_at = max(now, self._next_request_at) + self.interval

        if delay:
            self._sleep(delay)


class ScraperHttpClient:
    def __init__(
        self,
        config: ScraperHttpConfig,
        rate_limiter: RequestRateLimiter | None = None,
    ) -> None:
        self.config = config
        self.rate_limiter = rate_limiter
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
        if self.rate_limiter is not None:
            self.rate_limiter.wait()
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
