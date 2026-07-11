# Architecture

## Tech Stack

- Backend: Python, FastAPI, Pydantic
- Database: DynamoDB through boto3
- Scraping: Requests and BeautifulSoup
- Frontend: Next.js, React, TypeScript
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

## Jobs Frontend MVP

- The frontend lives in `frontend/` and uses Next.js with React and TypeScript.
- `frontend/app/page.tsx` is the initial jobs dashboard. It fetches stored jobs from the backend `GET /jobs` endpoint, keeps filtering client-side, and shows a selected-job detail pane.
- `frontend/lib/jobs.ts` owns the API call and reads `NEXT_PUBLIC_API_BASE_URL`, defaulting to `http://localhost:8000` for local development.
- `frontend/types/job.ts` mirrors the `JobRead` response from `backend/api/data/schemas.py`.
- `backend/api/data/schemas.py` now includes source website, source URL, and required languages in `JobRead` so the UI can display where each scraped job came from.
- `docker-compose.yaml` includes a `frontend` service on port `3000`. The browser talks to the FastAPI backend on `http://localhost:8000`, and the backend continues to read jobs from DynamoDB.

## jobs.ch Search Form

- The dashboard's primary search bar is exclusively a jobs.ch scrape launcher. Typing does not filter or otherwise modify the stored job list.
- `frontend/app/page.tsx` sends the search term, location, and one-to-five-page limit when the form is submitted or Enter is pressed. It displays progress, reports the run's found/created/updated counts, and refreshes the stored job list after success.
- A separate, explicitly labeled local-filter panel narrows stored jobs by keywords and location without making a scraper request. Its filters can be cleared independently and the dashboard shows both stored and currently visible counts.
- `frontend/lib/jobs.ts` sends the form as JSON to `POST /jobs/scrape/jobs-ch` and converts unsuccessful API responses into user-visible errors. Both listing and scraping use `NEXT_PUBLIC_API_BASE_URL`, with local port `8000` as the fallback.
- `frontend/types/job.ts` mirrors the scrape request and scrape-run response schemas so the UI-to-API flow remains type-safe.
