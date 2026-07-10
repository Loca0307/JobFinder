from __future__ import annotations

from abc import ABC, abstractmethod

from api.data.schemas import NormalizedJob


# Abstract class used to implement scrapers
class BaseJobScraper(ABC):
    source_name: str
    base_url: str

    # Abstract methods with base data filter for scraping
    @abstractmethod
    def scrape(
        self,
        search_term: str | None = None, # String to filter jobs like "Software engineer"
        location: str | None = None, 
        pages: int = 1,
    ) -> list[NormalizedJob]:
        """Return normalized jobs without persisting them."""
