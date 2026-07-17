from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from api.settings.config import get_settings
from api.data.models import (
    job_partition_key,
    make_job_item,
    make_scrape_run_item,
    make_source_item,
)
from api.data.schemas import NormalizedJob
from api.services.location_normalization import normalize_location


def get_jobs_table():
    settings = get_settings()
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
    )
    return dynamodb.Table(settings.dynamodb_jobs_table)


def count_jobs() -> int:
    table = get_jobs_table()
    scan_args: Dict[str, Any] = {
        "FilterExpression": "item_type = :item_type",
        "ExpressionAttributeValues": {":item_type": "JOB"},
        "Select": "COUNT",
    }
    count = 0

    while True:
        response = table.scan(**scan_args)
        count += response.get("Count", 0)
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return count
        scan_args["ExclusiveStartKey"] = last_key


def list_jobs(
    limit: int = 50,
    query: Optional[str] = None,
    location: Optional[str] = None,
) -> List[Dict[str, Any]]:
    table = get_jobs_table()
    query_text = (query or "").strip().casefold()
    location_text = normalize_location(location).casefold()
    scan_args: Dict[str, Any] = {
        "FilterExpression": "item_type = :item_type",
        "ExpressionAttributeValues": {":item_type": "JOB"},
    }
    if not query_text and not location_text:
        scan_args["Limit"] = limit

    items: List[Dict[str, Any]] = []
    while True:
        response = table.scan(**scan_args)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key or (not query_text and not location_text):
            break
        scan_args["ExclusiveStartKey"] = last_key

    matching_items = [
        item
        for item in items
        if (
            not query_text
            or query_text
            in " ".join(
                str(item.get(field, ""))
                for field in ("title", "company", "description", "requirements")
            ).casefold()
        )
        and (
            not location_text
            or location_text in str(item.get("location", "")).casefold()
        )
    ]
    return sorted(
        matching_items,
        key=lambda item: item.get("created_at", ""),
        reverse=True,
    )[:limit]

# Makes sure that a source and url is saved in the db
def get_or_create_source(name: str, base_url: str) -> Dict[str, Any]:
    table = get_jobs_table()
    source = make_source_item(name, base_url)
    try:
        table.put_item(
            Item=_clean_item(source),
            ConditionExpression="attribute_not_exists(PK)",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
    return source


def start_scrape_run(
    source_name: str,
    search_term: Optional[str],
    location: Optional[str],
    pages: int,
) -> Dict[str, Any]:
    table = get_jobs_table()
    run = make_scrape_run_item(source_name, search_term, location, pages)
    table.put_item(Item=_clean_item(run))
    return run


# Adds or updates scraper results in the db
def upsert_jobs(jobs: List[NormalizedJob]) -> Tuple[int, int]:
    table = get_jobs_table()
    created = 0
    updated = 0

    for normalized_job in jobs:
        content_hash = _job_hash(normalized_job)
        source_url = str(normalized_job.source_url)
        key = {
            "PK": job_partition_key(normalized_job.source_website, source_url),
            "SK": "METADATA",
        }
        existing = table.get_item(Key=key).get("Item")
        item = make_job_item(normalized_job, content_hash)

        if existing is None:
            table.put_item(Item=_clean_item(item))
            created += 1
            continue

        if existing.get("content_hash") != content_hash:
            item["created_at"] = existing.get("created_at", item["created_at"])
            table.put_item(Item=_clean_item(item))
            updated += 1

    return created, updated


def finish_scrape_run(
    run: Dict[str, Any],
    status: str,
    jobs_found: int,
    jobs_created: int,
    jobs_updated: int,
    job_ids: Optional[List[str]] = None,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    table = get_jobs_table()
    run.update(
        {
            "status": status,
            "jobs_found": jobs_found,
            "jobs_created": jobs_created,
            "jobs_updated": jobs_updated,
            "job_ids": job_ids or [],
            "error_message": error_message,
        }
    )
    run["finished_at"] = run.get("finished_at") or _utc_now_iso()
    table.put_item(Item=_clean_item(run))
    return run


def _job_hash(job: NormalizedJob) -> str:
    content = "|".join(
        [
            job.title,
            job.company or "",
            job.location or "",
            job.description or "",
            job.requirements or "",
            job.seniority or "",
            job.employment_type or "",
            job.remote_type or "",
            job.salary or "",
            ",".join(job.required_languages),
        ]
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _utc_now_iso() -> str:
    from api.data.models import utc_now_iso

    return utc_now_iso()


def _clean_item(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean_item(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_clean_item(item) for item in value]
    if isinstance(value, float):
        return Decimal(str(value))
    return value
