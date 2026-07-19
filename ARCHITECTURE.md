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
- GitHub Actions authenticates with short-lived AWS credentials through OIDC using the `AWS_DEPLOY_ROLE_ARN` repository variable. `tf/gh_action_backend.tf` provisions the repository-and-branch-scoped OIDC trust plus a role limited to updating and reading the existing Lambda function.
- Terraform remains the source of truth for infrastructure and Lambda configuration. It is applied separately because this repository currently uses local Terraform state; the workflow changes Lambda code only.

## Frontend Deployment Workflow

- `.github/workflows/update-frontend.yaml` deploys frontend changes pushed to `main` and supports manual runs.
- GitHub Actions installs the locked frontend dependencies with Node.js 22 and runs the Next.js static export with `NEXT_PUBLIC_API_BASE_URL` supplied by a repository variable.
- The generated `frontend/out/` contents are synchronized to the private `job-finder-static` bucket under `out/`, matching the CloudFront origin path, and obsolete objects are deleted.
- After upload, the workflow invalidates `/*` on CloudFront distribution `E2U4YDALK1V35D` so the new static assets are served immediately.
- `tf/gh_action_frontend.tf` provisions a separate repository-scoped OIDC role for the frontend workflow. Its policy can list only the configured frontend bucket, manage only objects under `out/`, and create invalidations only for the configured CloudFront distribution. The workflow assumes this role through the `AWS_FRONTEND_DEPLOY_ROLE_ARN` repository variable, keeping frontend permissions separate from the Lambda deployment role.

## jobs.ch Job Scraping Foundation

- The first scraping source is `jobs.ch`, a JobCloud platform and one of Switzerland's main job boards.
- Scrapers are independent classes under `backend/api/scrapers/` and return normalized `NormalizedJob` objects instead of writing directly to the database.
- `backend/api/scrapers/jobs_ch.py` builds jobs.ch listing URLs and parses the public page's embedded `__INIT__` JSON into lightweight summaries containing ID, title, company, location, date, and URL. Search never opens every detail page. The existing schema.org `JobPosting` and HTML fallback parsers are used only when one job's details are requested.
- `backend/api/scrapers/base.py` owns the reusable page-concurrency flow. Every `PaginatedJobScraper` inherits a five-page default, while non-paginated sources keep their own natural request count. The coordinator runs the source-specific `_scrape_page()` implementation through a bounded `ThreadPoolExecutor`, preserves jobs from successful pages, restores page order, and deduplicates by source URL. If every requested page fails it raises `ScrapeError`, allowing multi-source orchestration to report a real source failure instead of a successful empty result. New page-based scrapers only implement page fetch/parsing logic. Worker count is configured with `SCRAPER_MAX_WORKERS` and capped by the requested page count.
- `backend/api/scrapers/http.py` provides the shared scraper HTTP layer. `ScraperHttpConfig` carries headers, separate connection/read timeouts, retry counts, backoff, and retryable status codes. `ScraperHttpClient` installs the same retry-enabled adapter for HTTP and HTTPS, respects `Retry-After`, raises final HTTP errors, and closes its session through a context manager. Every jobs.ch page worker creates its own client without sharing a session between threads.
- All clients created for one jobs.ch scraper share a thread-safe `RequestRateLimiter`. It reserves request start times across listing and detail requests before network access, so adding workers improves overlap without multiplying pressure on the source. `SCRAPER_REQUESTS_PER_SECOND` controls the source-wide rate, defaults to two requests per second, and can be set to zero to disable limiting.
- `backend/api/data/schemas.py` defines the normalized job, live-search response, and user interaction contracts shared by the backend and frontend.
- `backend/api/services/job_attribute_extraction.py` uses deterministic multilingual patterns to derive normalized seniority, required languages, and remote type from each job's title and description. The jobs.ch JSON-LD and HTML-fallback flows call it before constructing `NormalizedJob`; title terms take priority over description matches, languages are deduplicated into canonical English names, and remote arrangements use `remote`, `hybrid`, or `on_site`. Structured schema.org `jobLocationType` is preferred when present, while contextual patterns distinguish working arrangements from terms such as hybrid cloud.
- `backend/api/services/scrape_orchestration.py` deduplicates the final combined `NormalizedJob` list across all successful sources. Its conservative vacancy fingerprint normalizes case, punctuation, whitespace, and known location aliases across title, company, and location, allowing the same vacancy under different board URLs to collapse while retaining identical roles advertised in different cities. Per-source counts remain diagnostic raw counts; the aggregate `jobs_found` reflects the deduplicated jobs returned to the frontend.
- `backend/tests/test_jobs_ch_scraper.py` exercises the scraper without live network access. It covers summary JSON extraction, absence of detail requests during search, on-demand detail URL construction, JSON-LD and HTML detail parsing, simultaneous five-page execution, deterministic deduplication, and failure isolation.
- `backend/tests/test_scraper_http.py` verifies shared headers, HTTP/HTTPS retry adapter configuration, retryable statuses, `Retry-After` support, connect/read timeout forwarding, HTTP status checking, and context-managed session cleanup without making live network requests.
- `backend/tests/test_scraper_concurrency_performance.py` compares five simulated slow page operations sequentially and through the real scraper coordinator. It uses deterministic local delays rather than live network timing and requires the five-worker execution to complete in less than 60% of the sequential duration.
- `backend/api/routes/jobs.py` exposes live multi-source search at `POST /jobs/scrape` and user tracking at `GET`/`PUT /jobs/interactions`.
- `backend/api/scrapers/jobs_ch.py` exposes a cached scraper factory used by `backend/api/routes/jobs.py`. Every scrape request handled by one backend process therefore reuses the same `JobsChScraper`, including its shared rate limiter, instead of constructing independent limiters that could overlap. The factory initializes lazily so application environment loading completes before scraper settings are read.
- `docker-compose.yaml` runs DynamoDB Local on host port `8001`, passes dummy local AWS credentials to the backend, and points `DYNAMODB_ENDPOINT_URL` at the Compose service. In deployed AWS/Lambda usage, omit `DYNAMODB_ENDPOINT_URL` and provision the table as infrastructure.

## DynamoDB Terraform

- `tf/dynamodb.tf` provisions the AWS DynamoDB table required by the backend.
- The table uses the same single-table key schema as the Python item builders:
  - `PK` string partition key.
  - `SK` string sort key.
- Billing is `PAY_PER_REQUEST` so the MVP does not need capacity planning.
- Point-in-time recovery and server-side encryption are enabled.
- The default table name is `Jobs`, matching local Docker Compose and the backend `DYNAMODB_JOBS_TABLE` environment variable.
- Terraform outputs the table name and ARN for Lambda configuration and IAM wiring.

## Jobs Frontend MVP

- The frontend lives in `frontend/` and uses Next.js with React and TypeScript.
- `frontend/app/page.tsx` presents live results from both sources and a starred-jobs view. `frontend/hooks/useJobsDashboard.ts` owns live results, interaction state, selection, and errors.
- `frontend/lib/jobs.ts` calls the live-search and interaction endpoints using `NEXT_PUBLIC_API_BASE_URL`, defaulting to `http://localhost:8000` locally.
- Job details provide an external Apply link, a separate explicit “Mark as applied” action, and star/unstar. Opening Apply alone never writes an interaction.
- jobs.ch summaries carry `details_loaded=false`. Selecting one calls `GET /jobs/jobs-ch/{external_id}`, replaces that summary in both visible results and the local cache, and enables star/applied actions only after the complete snapshot arrives. SwissDevJobs entries are complete from their RSS feed and skip this request.
- The live-search term, location, and most recent result list are restored from browser `localStorage` after a refresh. Refreshing displays the cached jobs without scraping again; a new search replaces the cache, and the Clear button removes the stored search and results.

## Live Job Search and User Interactions

- `POST /jobs/scrape` runs jobs.ch and SwissDevJobs concurrently and returns normalized jobs directly. Search orchestration performs no DynamoDB writes; source counts and failures go through Python logging to CloudWatch in Lambda.
- Stable job IDs are derived from source name and canonical source URL. They identify interaction records without requiring a global stored-job index.
- DynamoDB stores only user interactions at `PK = USER#<user-id>` and `SK = JOB#<job-id>`. Each `JOB_INTERACTION` contains a complete display snapshot, `starred`, `applied`, and timestamps. The current server-side user is `default`, leaving the key layout ready for authenticated users.
- `GET /jobs/interactions` queries tracked jobs. `PUT /jobs/interactions/{job_id}` handles star, unstar, and explicit applied confirmation; when both flags are false it deletes the record, while unstarred applied jobs remain.
- Component styling uses Tailwind utility classes. `frontend/postcss.config.mjs` enables the Tailwind 4 PostCSS plugin, while `frontend/app/globals.css` only imports Tailwind instead of maintaining page-specific selectors.
- jobs.ch JSON-LD requirements may be either text or a list; the scraper flattens both forms before HTML removal so valid specialist jobs are not discarded during normalization.
- Before constructing a jobs.ch listing URL, the scraper normalizes common English, Italian, and French Swiss-city exonyms (for example, `zurigo` and `Zurich`) to the location names indexed by jobs.ch (`Zürich`).

## SwissDevJobs RSS Scraping

- `backend/api/scrapers/swiss_dev_jobs.py` implements the second job source through SwissDevJobs' public RSS feed. One request retrieves the feed, Python's standard XML parser reads its entries, and BeautifulSoup converts the embedded HTML sections into normalized requirements, responsibilities, technologies, salary, company, publication date, and job links.
- RSS tracking parameters are removed before normalization so the same vacancy keeps a stable ID and interaction key.
- Keyword filtering runs locally across the normalized title, company, description, requirements, technologies, and original RSS text. Location aliases use the shared Swiss location normalizer and must appear in the entry text; an entry without matching location evidence is excluded when a location was requested.
- `backend/api/services/scrape_orchestration.py` runs jobs.ch and SwissDevJobs concurrently while each scraper retains its own HTTP client and rate limiter. A single-source failure produces aggregate status `partial`; HTTP 502 is returned only when every source fails.
- The frontend search form calls the unified endpoint and renders both sources through the same `Job` type, list, and details components. Existing source badges identify where each result originated without requiring a source selector.
- `backend/tests/test_swiss_dev_jobs_scraper.py` covers RSS parsing, canonical URLs, normalized attributes, local keyword and location filters, deduplication, and single-request feed access. `backend/tests/test_scrape_orchestration.py` covers complete success, partial success, and total failure across sources.
