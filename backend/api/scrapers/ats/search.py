from __future__ import annotations

import re
import unicodedata

from api.data.schemas import NormalizedJob
from api.services.location_normalization import normalize_location
from api.services.swiss_territory import normalize_country_code


def matches_search(
    job: NormalizedJob,
    search_term: str | None,
    location: str | None,
) -> bool:
    """Apply JobFinder's live query to a complete ATS feed item."""
    if search_term and _words(search_term) not in _words(
        " ".join(
            filter(
                None,
                (
                    job.title,
                    job.company,
                    job.description,
                    job.requirements,
                ),
            )
        )
    ):
        return False

    if not location:
        return True

    requested_location = normalize_location(location)
    if normalize_country_code(requested_location) == "CH":
        return job.country_code == "CH"
    return _words(requested_location) in _words(job.location or "")


def _words(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[^\W_]+", without_accents, re.UNICODE))
