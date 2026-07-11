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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Cache that removes least recently used data
@lru_cache
def get_settings() -> Settings:
    return Settings()
