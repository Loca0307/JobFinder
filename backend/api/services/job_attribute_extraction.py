from __future__ import annotations

import re

# Regex-based normalization of attributes found in a job title or description.

_SENIORITY_PATTERNS = (
    ("executive", r"\b(?:chief|c-level|executive)\b"),
    ("director", r"\b(?:director|direktor(?:in)?|directeur|direttrice|direttore)\b"),
    ("manager", r"\b(?:manager|management)\b"),
    ("lead", r"\b(?:lead|team lead|tech lead|principal|staff|head of)\b"),
    ("senior", r"\b(?:senior|sr\.?|experienced|erfahren(?:e[rsnm]?)?|expérimenté(?:e)?|esperto|esperta)\b"),
    ("mid_level", r"\b(?:mid[ -]?level|intermediate)\b"),
    ("junior", r"\b(?:junior|jr\.?)\b"),
    ("entry_level", r"\b(?:entry[ -]?level|graduate|berufseinsteiger(?:in)?)\b"),
    ("internship", r"\b(?:intern(?:ship)?|trainee|stagiaire|stage|praktik(?:ant|antin|um)|tirocin(?:ante|io))\b"),
)

_LANGUAGE_PATTERNS = (
    ("English", r"\b(?:english|englisch|anglais|inglese)\b"),
    ("German", r"\b(?:german|deutsch|allemand|tedesco)\b"),
    ("French", r"\b(?:french|fran[çc]ais(?:e)?|französisch|francese)\b"),
    ("Italian", r"\b(?:italian|italiano|italiana|italienisch|italien)\b"),
    ("Romansh", r"\b(?:romansh|romansch|rumantsch|romancio)\b"),
    ("Spanish", r"\b(?:spanish|español|espagnol|spanisch|spagnolo)\b"),
)

_REMOTE_TYPE_PATTERNS = (
    (
        "on_site",
        r"\b(?:no remote|not remote|remote (?:work )?(?:is )?not (?:available|possible)|kein home[ -]?office)\b",
    ),
    (
        "hybrid",
        r"\b(?:hybrid(?:e[nsr]?)? (?:role|setup|work(?:ing)?|conditions?|contract|arrangement|model)|ibrid[oa] (?:ruolo|lavoro)|partly remote|partially remote|teilweise remote|hybrid zu arbeiten|home[ -]?office[ -]?(?:option|möglichkeit)|möglichkeit.{0,30}home[ -]?office|possibility (?:for|of).{0,20}home[ -]?office|mix.{0,30}home[ -]?office|home[ -]?office by arrangement|\d+/?\d* (?:of )?(?:the )?(?:working )?(?:days?|time).{0,20}home[ -]?office|home[ -]?office.{0,20}\d+ days?)\b",
    ),
    (
        "remote",
        r"\b(?:fully remote|remote (?:position|role|work|working)|remote zu arbeiten|work(?:ing)? from home|home[ -]?based|telework|télétravail|fernarbeit|remoto)\b",
    ),
    (
        "on_site",
        r"\b(?:on[ -]?site|office[ -]?based|in[ -]?office|presence required|vor ort|sur site|in sede)\b",
    ),
)


def extract_seniority(title: str | None, description: str | None) -> str | None:
    """Return a normalized seniority, preferring explicit terms in the title."""
    for text in (title, description):
        if not text:
            continue
        for seniority, pattern in _SENIORITY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return seniority
    return None


def extract_required_languages(
    title: str | None, description: str | None
) -> list[str]:
    """Return canonical language names mentioned in the title or description."""
    text = " ".join(part for part in (title, description) if part)
    return [
        language
        for language, pattern in _LANGUAGE_PATTERNS
        if re.search(pattern, text, re.IGNORECASE)
    ]


def extract_remote_type(title: str | None, description: str | None) -> str | None:
    """Return remote, hybrid, or on_site, preferring explicit title wording."""
    if title and re.search(r"\bremote\b", title, re.IGNORECASE):
        return "remote"
    for text in (title, description):
        if not text:
            continue
        for remote_type, pattern in _REMOTE_TYPE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return remote_type
    return None


def normalize_structured_remote_type(value: str | None) -> str | None:
    """Normalize schema.org jobLocationType values when jobs.ch provides one."""
    if not value:
        return None
    if re.search(r"\b(?:telecommute|working from home|remote)\b", value, re.IGNORECASE):
        return "remote"
    if re.search(r"\bhybrid\b", value, re.IGNORECASE):
        return "hybrid"
    return None
