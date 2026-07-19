from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from boto3.dynamodb.conditions import Key

from api.data.models import user_partition_key
from api.data.schemas import JobInteractionRead, JobInteractionWrite
from api.services.dynamodb import get_jobs_table

DEFAULT_USER_ID = "default"


def list_job_interactions(
    user_id: str = DEFAULT_USER_ID,
) -> list[JobInteractionRead]:
    table = get_jobs_table()
    query_args: dict[str, Any] = {
        "KeyConditionExpression": Key("PK").eq(user_partition_key(user_id)),
    }
    items: list[dict[str, Any]] = []
    while True:
        response = table.query(**query_args)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_args["ExclusiveStartKey"] = last_key

    interactions = [
        JobInteractionRead.model_validate(item)
        for item in items
        if item.get("item_type") == "JOB_INTERACTION"
    ]
    return sorted(interactions, key=lambda item: item.updated_at, reverse=True)


def save_job_interaction(
    job_id: str,
    interaction: JobInteractionWrite,
    user_id: str = DEFAULT_USER_ID,
) -> JobInteractionRead | None:
    table = get_jobs_table()
    key = {
        "PK": user_partition_key(user_id),
        "SK": f"JOB#{job_id}",
    }
    existing = table.get_item(Key=key).get("Item") or {}
    applied = interaction.applied or bool(existing.get("applied"))

    if not interaction.starred and not applied:
        table.delete_item(Key=key)
        return None

    now = _utc_now()
    item: dict[str, Any] = {
        **key,
        "item_type": "JOB_INTERACTION",
        "job": interaction.job.model_dump(mode="json", exclude_none=True),
        "starred": interaction.starred,
        "applied": applied,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }
    if applied:
        item["applied_at"] = existing.get("applied_at", now)

    table.put_item(Item=item)
    return JobInteractionRead.model_validate(item)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
