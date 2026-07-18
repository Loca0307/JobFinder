from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from api.data.schemas import NormalizedJob

# -------- Helper methods for data setting --------

def utc_now_iso() -> str:
    return datetime.now().isoformat() + "Z"



def new_id() -> str:
    return str(uuid.uuid4())


def job_id(source_website: str, source_url: str) -> str:
    source_key = source_website.strip().lower()
    url_hash = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
    return f"{source_key}#{url_hash}"


def job_partition_key(source_website: str, source_url: str) -> str:
    return f"JOB#{job_id(source_website, source_url)}"


def source_partition_key(source_name: str) -> str:
    return f"SOURCE#{source_name.strip().lower()}"


def scrape_run_partition_key(run_id: str) -> str:
    return f"SCRAPE_RUN#{run_id}"


def make_source_item(name: str, base_url: str) -> Dict[str, Any]:
    return {
        "PK": source_partition_key(name),
        "SK": "METADATA",
        "item_type": "SOURCE",
        "id": name.strip().lower(),
        "name": name,
        "base_url": base_url,
        "country": "CH",
        "created_at": utc_now_iso(),
    }


def make_scrape_run_item(
    source_name: str,
    search_term: Optional[str],
    location: Optional[str],
    pages: int,
) -> Dict[str, Any]:
    run_id = new_id()
    return {
        "PK": scrape_run_partition_key(run_id),
        "SK": "METADATA",
        "item_type": "SCRAPE_RUN",
        "id": run_id,
        "source_id": source_name.strip().lower(),
        "source_website": source_name,
        "status": "running",
        "search_term": search_term,
        "location": location,
        "pages_requested": pages,
        "jobs_found": 0,
        "jobs_created": 0,
        "jobs_updated": 0,
        "error_message": None,
        "started_at": utc_now_iso(),
        "finished_at": None,
    }


# Uses db schema and model processes to create the final item to store in the db
def make_job_item(job: NormalizedJob, content_hash: str) -> Dict[str, Any]:
    source_url = str(job.source_url)
    now = utc_now_iso()
    return {
        "PK": job_partition_key(job.source_website, source_url),
        "SK": "METADATA",
        "item_type": "JOB",
        "id": job_id(job.source_website, source_url),
        "external_id": job.external_id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": job.description,
        "requirements": job.requirements,
        "seniority": job.seniority,
        "employment_type": job.employment_type,
        "remote_type": job.remote_type,
        "salary": job.salary,
        "required_languages": job.required_languages,
        "source_website": job.source_website,
        "source_url": source_url,
        "apply_url": str(job.apply_url) if job.apply_url else None,
        "posting_date": job.posting_date.isoformat() if job.posting_date else None,
        "scrape_timestamp": job.scrape_timestamp.isoformat(),
        "content_hash": content_hash,
        "raw_payload": job.raw_payload,
        "created_at": now,
        "updated_at": now,
    }
