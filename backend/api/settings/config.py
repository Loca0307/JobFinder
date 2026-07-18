from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# AWS dyamo db settings
class Settings(BaseSettings):
    dynamodb_jobs_table: str = Field(default="Jobs", alias="DYNAMODB_JOBS_TABLE")
    dynamodb_endpoint_url: Optional[str] = Field(default=None, alias="DYNAMODB_ENDPOINT_URL")
    aws_region: str = Field(default="eu-central-1", alias="AWS_REGION")
    scraper_user_agent: str = Field(
        default=(
            "JobFinderBot/0.1 "
            "(contact: local-development; purpose: Swiss job search aggregation)"
        ),
        alias="SCRAPER_USER_AGENT",
    )
    scraper_timeout_seconds: int = Field(default=20, alias="SCRAPER_TIMEOUT_SECONDS")
    scraper_connect_timeout_seconds: float = Field(
        default=5, ge=0.1, alias="SCRAPER_CONNECT_TIMEOUT_SECONDS"
    )
    scraper_read_timeout_seconds: float = Field(
        default=15, ge=0.1, alias="SCRAPER_READ_TIMEOUT_SECONDS"
    )
    scraper_max_retries: int = Field(
        default=3, ge=0, alias="SCRAPER_MAX_RETRIES"
    )
    scraper_retry_backoff_factor: float = Field(
        default=1, ge=0, alias="SCRAPER_RETRY_BACKOFF_FACTOR"
    )
    scraper_max_workers: int = Field(
        default=5, ge=1, alias="SCRAPER_MAX_WORKERS"
    )
    scraper_requests_per_second: float = Field(
        default=2, ge=0, alias="SCRAPER_REQUESTS_PER_SECOND"
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Cache that removes least recently used data
@lru_cache
def get_settings() -> Settings:
    return Settings()
