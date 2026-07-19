from __future__ import annotations

import hashlib


def job_id(source_website: str, source_url: str) -> str:
    source_key = source_website.strip().lower()
    url_hash = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
    return f"{source_key}#{url_hash}"


def user_partition_key(user_id: str) -> str:
    return f"USER#{user_id.strip().lower()}"
