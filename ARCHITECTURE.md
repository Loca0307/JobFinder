# Architecture

## Tech Stack

- Backend: Python, FastAPI, Pydantic
- Database: DynamoDB through boto3
- Scraping: Requests, urllib3 retry policies, and BeautifulSoup
- Frontend: Next.js, React, TypeScript, Tailwind CSS 4 with PostCSS
- Deployment: Docker Compose, Terraform, AWS Lambda (Python 3.11)
- Existing AI dependencies: LangGraph, LangChain OpenAI

## Lambda Code Deployment Workflow

- `.github/workflows/update-lambda.yaml` deploys backend-only changes pushed to `main` and also supports manual runs.
- The workflow builds a Python 3.11 ZIP from `backend/main.py`, `backend/api/`, and `backend/requirements.txt`, matching the Lambda runtime managed in `tf/lambda.tf`, then updates the existing `JobFinder-fastapi` function.
- GitHub Actions authenticates with short-lived AWS credentials through OIDC using the `AWS_DEPLOY_ROLE_ARN` repository secret. `tf/github_actions.tf` provisions the repository-and-branch-scoped OIDC trust plus a role limited to updating and reading the existing Lambda function.
- Terraform remains the source of truth for infrastructure and Lambda configuration. It is applied separately because this repository currently uses local Terraform state; the workflow changes Lambda code only.

## Frontend Deployment Workflow

- `.github/workflows/update-frontend.yaml` deploys frontend changes pushed to `main` and supports manual runs.
- GitHub Actions installs the locked frontend dependencies with Node.js 22 and runs the Next.js static export with `NEXT_PUBLIC_API_BASE_URL` supplied by a repository variable.
- The generated `frontend/out/` contents are synchronized to the private `job-finder-static` bucket under `out/`, matching the CloudFront origin path, and obsolete objects are deleted.
- After upload, the workflow invalidates `/*` on CloudFront distribution `E2U4YDALK1V35D` so the new static assets are served immediately.
- `tf/github_actions.tf` grants the existing repository-scoped OIDC role access only to the frontend bucket objects, bucket listing, and this distribution's invalidations.

## jobs.ch Job Scraping Foundation

- The first scraping source is `jobs.ch`, a JobCloud platform and one of Switzerland's main job boards.
- Scrapers are independent classes under `backend/api/scrapers/` and return normalized `NormalizedJob` objects instead of writing directly to the database.
- `backend/api/scrapers/jobs_ch.py` builds jobs.ch listing URLs, extracts detail-page URLs, then parses schema.org `JobPosting` JSON-LD when present. It falls back to basic HTML extraction if no JSON-LD is available.
- `backend/api/scrapers/base.py` owns the reusable page-concurrency flow. `PaginatedJobScraper.scrape()` defaults to five pages and runs the source-specific `_scrape_page()` implementation through a bounded `ThreadPoolExecutor`, isolates worker failures, restores page order, and deduplicates jobs by source URL. New page-based scrapers inherit it and only implement their page fetch and parsing logic; non-paginated sources can still implement the smaller `BaseJobScraper` contract directly. Worker count is configured with `SCRAPER_MAX_WORKERS` and is capped by the requested page count.
- `backend/api/scrapers/http.py` provides the shared scraper HTTP layer. `ScraperHttpConfig` carries headers, separate connection/read timeouts, retry counts, backoff, and retryable status codes. `ScraperHttpClient` installs the same retry-enabled adapter for HTTP and HTTPS, respects `Retry-After`, raises final HTTP errors, and closes its session through a context manager. Every jobs.ch page worker creates its own client, safely reusing one connection pool for that page's listing and detail requests without sharing a session between threads.
- All clients created for one jobs.ch scraper share a thread-safe `RequestRateLimiter`. It reserves request start times across listing and detail requests before network access, so adding workers improves overlap without multiplying pressure on the source. `SCRAPER_REQUESTS_PER_SECOND` controls the source-wide rate, defaults to two requests per second, and can be set to zero to disable limiting.
- `backend/api/data/schemas.py` defines the normalized job contract used between scraper, ingestion service, and API.
- `backend/api/data/models.py` defines plain DynamoDB item builders:
  - `SOURCE#<source>` items store configured job boards such as jobs.ch.
  - `JOB#<source>#<source-url-hash>` items store normalized job offers with title, company, location, description, requirements, employment type, salary, language list, source URL, apply URL, posting date, scrape timestamp, raw payload, and content hash.
  - `SCRAPE_RUN#<uuid>` items record each run, its filters, status, counts, and errors.
- `backend/api/services/job_ingestion.py` owns DynamoDB ingestion through boto3. It creates source items, starts and finishes scrape runs, computes content hashes, and deduplicates jobs by deterministic source URL keys.
- `backend/api/services/job_attribute_extraction.py` uses deterministic multilingual patterns to derive normalized seniority, required languages, and remote type from each job's title and description. The jobs.ch JSON-LD and HTML-fallback flows call it before constructing `NormalizedJob`; title terms take priority over description matches, languages are deduplicated into canonical English names, and remote arrangements use `remote`, `hybrid`, or `on_site`. Structured schema.org `jobLocationType` is preferred when present, while contextual patterns distinguish working arrangements from terms such as hybrid cloud.
- The ingestion content hash includes extracted seniority, remote type, and required languages, ensuring a repeat scrape updates older DynamoDB jobs when attribute-extraction rules add or change normalized values.
- `backend/tests/test_jobs_ch_scraper.py` exercises the scraper without live network access. It covers listing URL construction and location normalization, multilingual detail-link extraction, malformed JSON-LD handling, structured field normalization, the HTML fallback, simultaneous execution of five page workers, independent worker sessions, deterministic cross-page deduplication, and isolation of listing, detail, and worker failures.
- `backend/tests/test_scraper_http.py` verifies shared headers, HTTP/HTTPS retry adapter configuration, retryable statuses, `Retry-After` support, connect/read timeout forwarding, HTTP status checking, and context-managed session cleanup without making live network requests.
- `backend/tests/test_scraper_concurrency_performance.py` compares five simulated slow page operations sequentially and through the real scraper coordinator. It uses deterministic local delays rather than live network timing and requires the five-worker execution to complete in less than 60% of the sequential duration.
- `backend/api/routes/jobs.py` exposes:
  - `GET /jobs` to list stored jobs.
  - `GET /jobs/health` as a jobs router smoke test.
  - `GET /jobs/scrape/jobs-ch` as a browser-friendly scrape trigger with query params.
  - `POST /jobs/scrape/jobs-ch` to run the first jobs.ch scraper and persist results.
- `backend/api/scrapers/jobs_ch.py` exposes a cached scraper factory used by `backend/api/routes/jobs.py`. Every scrape request handled by one backend process therefore reuses the same `JobsChScraper`, including its shared rate limiter, instead of constructing independent limiters that could overlap. The factory initializes lazily so application environment loading completes before scraper settings are read.
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
- `frontend/types/job.ts` mirrors the public `JobRead` response from `backend/api/data/schemas.py`; salary is omitted from both database-search responses and the frontend because the current job sources do not reliably provide it.
- `backend/api/data/schemas.py` now includes source website, source URL, and required languages in `JobRead` so the UI can display where each scraped job came from.
- `docker-compose.yaml` includes a `frontend` service on port `3000`. The browser talks to the FastAPI backend on `http://localhost:8000`, and the backend continues to read jobs from DynamoDB.

## jobs.ch Search Form

- The dashboard's primary search bar is exclusively a jobs.ch scrape launcher. Typing does not filter or otherwise modify the stored job list.
- `frontend/app/page.tsx` sends only the search term and location when the form is submitted or Enter is pressed. The backend always scrapes five pages, records that fixed count in the scrape run, and does not expose page selection in the public request schema. The UI displays progress, reports the run's found/created/updated counts, and refreshes the stored job list after success.
- A separate, explicitly labeled stored-job form submits keyword and location filters to `GET /jobs` without starting a scraper. Clicking its search button switches the result area to database mode and shows the backend-filtered matches; typing alone does not change the list.
- The dashboard starts with an empty result area. Each scrape run returns the normalized jobs' deterministic IDs and the frontend shows only that run's jobs, including unchanged jobs already present in DynamoDB. Clearing both fields in the scraper form switches the result area to stored-job mode, where the separate local filters apply.
- `frontend/lib/jobs.ts` sends the form as JSON to `POST /jobs/scrape/jobs-ch` and converts unsuccessful API responses into user-visible errors. Both listing and scraping use `NEXT_PUBLIC_API_BASE_URL`, with local port `8000` as the fallback.
- `frontend/types/job.ts` mirrors the scrape request and scrape-run response schemas so the UI-to-API flow remains type-safe.
- The dashboard UI is split into focused modules under `frontend/components/jobs/`: independent scraper and database forms, job list, and job details. `frontend/hooks/useJobsDashboard.ts` owns API calls and the single displayed-result collection, leaving `frontend/app/page.tsx` as a thin composition layer.
- One global clear action resets both forms, the shared job results, selected job, run summary, and errors without making an API request. The header shows the current result count and loads the total stored job count from `GET /jobs/count`, refreshing it after each scrape.
- Component styling uses Tailwind utility classes. `frontend/postcss.config.mjs` enables the Tailwind 4 PostCSS plugin, while `frontend/app/globals.css` only imports Tailwind instead of maintaining page-specific selectors.
- jobs.ch JSON-LD requirements may be either text or a list; the scraper flattens both forms before HTML removal so valid specialist jobs are not discarded during normalization.
- Before constructing a jobs.ch listing URL, the scraper normalizes common English, Italian, and French Swiss-city exonyms (for example, `zurigo` and `Zurich`) to the location names indexed by jobs.ch (`Zürich`). The scrape-run record retains the user's original location input.
- `backend/api/services/location_normalization.py` provides the same canonical Swiss-city mapping to both jobs.ch scraping and stored DynamoDB searches, so equivalent inputs such as `zurigo`, `zurich`, and `Zürich` match consistently.
- Stored-job listing paginates through the DynamoDB scan, orders the complete result by update time, and only then applies the requested UI limit. This prevents DynamoDB's arbitrary scan order from hiding newly ingested jobs.

## SwissDevJobs RSS Scraping

- `backend/api/scrapers/swiss_dev_jobs.py` implements the second job source through SwissDevJobs' public RSS feed. One request retrieves the feed, Python's standard XML parser reads its entries, and BeautifulSoup converts the embedded HTML sections into normalized requirements, responsibilities, technologies, salary, company, publication date, and job links.
- RSS tracking parameters are removed before normalization so the same vacancy keeps a stable source URL and DynamoDB key. The scraper sets `source_website` to `swissdevjobs.ch`; the existing source-aware job key therefore stores SwissDevJobs and jobs.ch vacancies in the same table without collisions between sources.
- Keyword filtering runs locally across the normalized title, company, description, requirements, technologies, and original RSS text. Location aliases use the shared Swiss location normalizer and must appear in the entry text; an entry without matching location evidence is excluded when a location was requested.
- `backend/api/services/scrape_orchestration.py` runs jobs.ch and SwissDevJobs concurrently while each scraper retains its own HTTP client and rate limiter. Each source creates and completes an independent scrape-run record, then successful normalized jobs flow through the shared DynamoDB ingestion service.
- `POST /jobs/scrape` is the source-neutral frontend endpoint. `ScrapeSummary` defines the counters shared by all scrape responses, `MultiSourceScrapeResult` adds the combined jobs and compact `sources` results, and `ScrapeRunRead` remains the detailed persisted-run response for the backward-compatible jobs.ch-only endpoint. If one source fails, its result is marked failed while the other source's jobs are stored and returned with aggregate status `partial`; the endpoint returns HTTP 502 only when every source fails.
- The frontend search form calls the unified endpoint and renders both sources through the same `Job` type, list, and details components. Existing source badges identify where each result originated without requiring a source selector.
- `backend/tests/test_swiss_dev_jobs_scraper.py` covers RSS parsing, canonical URLs, normalized attributes, local keyword and location filters, deduplication, and single-request feed access. `backend/tests/test_scrape_orchestration.py` covers complete success, partial success, and total failure across sources.
