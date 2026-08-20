# JobFinder

JobFinder is a project built with the idea to centralize hte job search in switzerland.

The long-term idea is a personal career agent that finds relevant roles,
explains why they match, identifies missing skills, and suggests practical ways
to close those gaps. This repository contains the first milestone:
a working Swiss job-search application that collects vacancies from multiple
sources, normalizes them behind one API, and lets a user review, save, and track
the jobs that matter.



## What is implemented

- Live search across **jobs.ch**, **jobup.ch**, **SwissDevJobs**, and selected
  company career sites
- Public Greenhouse and Lever API adapters for **Scandit**, **On**, **RIVR**,
  and **SwissBorg**
- A common job model shared by every source
- Concurrent source and page fetching with configurable limits
- Retries, timeouts, rate limiting, and isolated scraper failures
- Cross-source deduplication by normalized title, company, and location
- Lazy detail loading, so search does not open every vacancy page
- Deterministic extraction of seniority, languages, and remote-work type
- A responsive Next.js dashboard for searching and reviewing results
- Starred-job and application tracking
- Browser-side restoration of the latest search
- Automated backend tests using mocked network responses
- An AWS deployment path using Lambda, S3, CloudFront, DynamoDB, Terraform, and
  GitHub Actions with OIDC

## The decision that changed the architecture

I originally designed JobFinder around a DynamoDB catalogue containing every
scraped vacancy. It looked like the natural starting point: scrape first, store
everything, and query it later.

While building the search flow, I realized that this solved problems the MVP
did not yet have. Persisting every result introduced questions around expiry,
freshness, write volume, duplicate records and user search dynamics before the product had any need
for historical job data. It also meant that a live search could not simply be a
live search anymore—it became an ingestion pipeline.

I changed the design:

- Search results now travel directly from the scrapers to the user.
- The most recent search is cached in the browser to avoid scraping again on a
  refresh.
- DynamoDB is used only after a meaningful user action: starring a job or
  marking it as applied.
- Each saved interaction includes a snapshot of the job, so it remains useful
  even when the original listing disappears.

This was an important lesson from the project: choosing a technology is less
important than continually checking whether it still earns its complexity.
DynamoDB remains useful here, but in a much smaller and clearer role.

## How it works

```text
Next.js dashboard
       │
       ▼
FastAPI API ───────► scraper registry
                         ├── jobs.ch
                         ├── jobup.ch
                         ├── SwissDevJobs
                         └── company catalog (one source per target)
                              ├── Greenhouse: Scandit, On
                              └── Lever: RIVR, SwissBorg
                         │
                         ▼
              Swiss filter + deduplicate
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
       live search results     user chooses a job
             │                       │
       browser cache           DynamoDB interaction
```

The backend treats every scraper as an independent adapter. Each source returns
the same Pydantic model, which keeps source-specific parsing out of the API and
frontend.

The two JobCloud sources return lightweight summaries first. Full details are
requested only when a user opens a result. SwissDevJobs exposes an RSS feed.
Each catalogued company becomes an independent `company:<id>` source backed by
its public Greenhouse or Lever API, and returns complete jobs without a second
detail request. Company results are filtered locally by the requested keywords
and location, then retained only when structured country data or conservative
Swiss location evidence identifies them as Swiss vacancies. If a source or
page fails, the application preserves successful results and reports a partial
run instead of failing the entire search.

## Engineering decisions I would highlight

**Use structured data before scraping presentation HTML.** jobs.ch and
jobup.ch are parsed from embedded application data and schema.org job postings,
while company vacancies use public Greenhouse and Lever JSON APIs. HTML is kept
for job-description cleanup and the JobCloud fallback, avoiding unnecessary
coupling to presentation layouts.

**Be concurrent, but bounded.** Sources and paginated results are fetched in
parallel because the workload is network-bound. Worker limits and per-source
rate limiting keep that speedup controlled.

**Fail partially.** A change or outage on one external website should not hide
valid results from the others. Individual failures are isolated and returned as
diagnostics.

**Normalize at the boundary.** Scrapers produce one source-neutral model.
Location aliases, languages, seniority, remote type, IDs, and duplicates are
resolved before the data reaches the UI.

**Prefer deterministic logic before AI.** Attributes that can be extracted
reliably with multilingual rules are handled without an LLM. The planned AI
layer can then focus on genuinely semantic work such as fit, skill gaps, and
career recommendations.

**Load details only when they create value.** Fetching every vacancy page made
search slower and placed unnecessary load on external sites. Lazy loading cut
that work to the jobs a user actually examines.

More detailed reasoning, including alternatives considered, is recorded in
[CHOICES.md](CHOICES.md). The implemented flows are documented in
[ARCHITECTURE.md](ARCHITECTURE.md) and
[SCRAPER_WORKFLOW.md](SCRAPER_WORKFLOW.md).

## Technology

| Area | Tools |
| --- | --- |
| Backend | Python, FastAPI, Pydantic |
| Scraping | Requests, BeautifulSoup, urllib3 |
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Persistence | DynamoDB and browser `localStorage` |
| AWS | Lambda, S3, CloudFront, IAM |
| Delivery | Docker, Terraform, GitHub Actions |
| Testing | unittest, mocked HTTP and deterministic fixtures |

## Repository structure

```text
backend/
  api/
    routes/       # FastAPI endpoints
    scrapers/     # source adapters and shared HTTP behavior
      ats/        # Greenhouse, Lever, target validation, and local filtering
      company_targets.json
    services/     # orchestration, normalization, and interactions
    data/         # API and persistence models
  tests/
frontend/
  app/            # Next.js application
  components/     # search, list, and detail UI
  hooks/          # dashboard state and user workflow
tf/               # AWS infrastructure
```

## Running locally

The application can be started with Docker Compose:

```bash
docker compose up --build
```

The frontend is then available at `http://localhost:3000` and the FastAPI
service at `http://localhost:8000`.

The backend expects AWS credentials and a DynamoDB table named `Jobs` for
starred/applied interactions. The table uses string keys named `PK` and `SK`.
Live search itself does not require database writes. Company targets live in
`backend/api/scrapers/company_targets.json`; edit that validated catalog and
restart the backend to change company coverage.

To run the backend tests:

```bash
cd backend
python -m unittest discover -s tests -v
```

To check the production frontend build:

```bash
cd frontend
npm install
npm run build
```

Scraping depends on the current public structure of third-party websites.
Tests therefore use local fixtures and mocked requests instead of depending on
live sites.

## Current limits and next steps

The current build uses a single default user and shared Basic authentication
for a private staging deployment; it is not a production identity system.
Search is synchronous, rate limits are process-local, and browser-cached
results do not yet expire. Company coverage is a manually reviewed catalog and
currently supports only public Greenhouse and Lever boards; it does not bypass
login-only or blocked career systems.

The next branch of the project will build on this foundation with:

1. user profiles and proper authentication;
2. rule-based filtering followed by AI job-fit scoring;
3. explainable skill-gap analysis;
4. learning, certification, and portfolio-project recommendations; and
5. application history that can support a longer-term career workflow.

Those features are deliberately not presented as complete here. This milestone
is the retrieval and interaction layer on which they can be built.
