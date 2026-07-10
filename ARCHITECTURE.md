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
  - `POST /jobs/scrape/jobs-ch` to run the first jobs.ch scraper and persist results.
- `backend/main.py` includes the jobs router and stays Lambda-compatible through Mangum without SQL startup hooks.
- `docker-compose.yaml` passes AWS/DynamoDB table settings to the backend. The table is expected to exist in AWS for deployed usage.
