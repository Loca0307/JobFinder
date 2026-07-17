LOCATION_ALIASES = {
    "zurigo": "Zürich",
    "zurich": "Zürich",
    "ginevra": "Genève",
    "geneva": "Genève",
    "basilea": "Basel",
    "berna": "Bern",
    "lucerna": "Luzern",
    "lausanne": "Lausanne",
    "losanna": "Lausanne",
}


def normalize_location(value: str | None) -> str:
    if not value:
        return ""
    cleaned = value.strip()
    return LOCATION_ALIASES.get(cleaned.casefold(), cleaned)
