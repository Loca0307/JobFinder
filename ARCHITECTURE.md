# Architecture

## Tech Stack

- Backend: Python, FastAPI, Pydantic
- Database: DynamoDB through boto3
- Scraping: Requests and BeautifulSoup
- Deployment: Docker Compose
- Existing AI dependencies: LangGraph, LangChain OpenAI

## jobs.ch Job Scraping Foundation

- The first scraping source is `jobs.ch`, a JobCloud platform and one of Switzerland's main job boards.
- Scrapers are independent classes under `backend/api/scrapers/` and return normalized `NormalizedJob` objects instead of writing directly to the database.
- `backend/api/scrapers/jobs_ch.py` builds jobs.ch listing URLs, extracts detail-page URLs, then parses schema.org `JobPosting` JSON-LD when present. It falls back to basic HTML extraction if no JSON-LD is available.
- `backend/api/data/schemas.py` defines the normalized job contract used between scraper, ingestion service, and API.
- `backend/api/data/models.py` defines plain DynamoDB item builders:
  - `SOURCE#<source>` items store configured job boards such as jobs.ch.
  - `JOB#<source>#<source-url-hash>` items store normalized job offers with title, company, location, description, requirements, employment type, salary, language list, source URL, apply URL, posting date, scrape timestamp, raw payload, and content hash.
  - `SCRAPE_RUN#<uuid>` items record each run, its filters, status, counts, and errors.
- `backend/api/services/job_ingestion.py` owns DynamoDB ingestion through boto3. It creates source items, starts and finishes scrape runs, computes content hashes, and deduplicates jobs by deterministic source URL keys.
- `backend/api/routes/jobs.py` exposes:
  - `GET /jobs` to list stored jobs.
  - `GET /jobs/health` as a jobs router smoke test.
  - `GET /jobs/scrape/jobs-ch` as a browser-friendly scrape trigger with query params.
  - `POST /jobs/scrape/jobs-ch` to run the first jobs.ch scraper and persist results.
- `backend/main.py` includes:
  - `GET /` as a root health/discovery endpoint so Docker Compose can be checked in a browser.
  - `GET /scrape/jobs-ch` and `POST /scrape/jobs-ch` as compatibility aliases for the scraper route.
  - A startup call to `ensure_jobs_table()`, which only auto-creates the table when `DYNAMODB_ENDPOINT_URL` is set for local development.
- `docker-compose.yaml` runs DynamoDB Local on host port `8001`, passes dummy local AWS credentials to the backend, and points `DYNAMODB_ENDPOINT_URL` at the Compose service. In deployed AWS/Lambda usage, omit `DYNAMODB_ENDPOINT_URL` and provision the table as infrastructure.

## DynamoDB Terraform

- `backend/dynamodb.tf` provisions the AWS DynamoDB table required by the backend.
- The table uses the same single-table key schema as the Python item builders:
  - `PK` string partition key.
  - `SK` string sort key.
- Billing is `PAY_PER_REQUEST` so the MVP does not need capacity planning.
- Point-in-time recovery and server-side encryption are enabled.
- The default table name is `Jobs`, matching local Docker Compose and the backend `DYNAMODB_JOBS_TABLE` environment variable.
- The file also outputs:
  - `jobs_table_name` for Lambda environment configuration.
  - `jobs_table_arn` for infrastructure wiring.
  - `jobs_table_access_policy_json` for attaching DynamoDB permissions to the backend Lambda role.
