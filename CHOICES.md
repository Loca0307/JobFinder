# Architectural Choices

This document records the meaningful architectural and efficiency choices in
JobFinder. It describes the current implementation, why it fits the present
MVP, and the main alternatives available as the project grows.

## Private Staging Authentication and Origin Isolation

**Choice:** Put shared Basic authentication at CloudFront for the private
staging site, route browser API calls through a `/jobs/*` behavior, and use a
SigV4 Lambda Origin Access Control with an `AWS_IAM` Function URL.

**Why:** The static Next.js export cannot safely hold a backend secret. A
viewer-request function blocks unauthenticated users before cached content is
served, while OAC independently proves that API origin requests came from the
configured CloudFront distribution. Lambda remains the only component with
DynamoDB permissions. This is small enough for a few trusted testers and
closes the direct public Function URL.

**Other options:**

- Amazon Cognito: provides individual users, revocation, and JWT claims, but
  adds token and account lifecycle complexity that private staging does not
  yet need.
- A secret compiled into the frontend: simple but ineffective because browser
  bundles and network requests expose it.
- IP allowlisting: useful for fixed networks, but inconvenient for friends on
  changing residential and mobile addresses.
- Leaving the Lambda URL public and relying on CORS: CORS is a browser policy,
  not API authorization, and non-browser clients could bypass it.

## 1. Modular Monolith Backend

**Choice:** Use one FastAPI application, divided into routes, services,
scrapers, data models, and settings.

**Why:** It provides clear responsibility boundaries while keeping deployment,
local development, testing, and function calls simple. The modules can be
extracted later if their workloads diverge.

**Other options:**

- Microservices per scraper: independent scaling and deployment, but more
  network calls, infrastructure, observability, and failure modes.
- One Lambda per scraper: strong isolation, but requires orchestration and more
  deployment configuration.
- Unstructured monolith: quicker for a prototype, but tightly couples routes,
  scraping, and persistence.

## 2. Source-Neutral Scraper Contracts

**Choice:** Every source implements `BaseJobScraper` and returns
`NormalizedJob` objects. Detail loading is an optional `DetailJobScraper`
capability.

**Why:** The API, orchestrator, frontend, and future AI services do not need
source-specific branches. Sources only implement capabilities they support.

**Other options:**

- Source-specific endpoints and models: preserve source details, but spread
  source-specific logic across every consumer.
- One large mandatory scraper interface: uniform, but forces unsupported
  methods onto simple RSS or API sources.
- Dynamically installed scraper plugins: more extensible, but adds discovery,
  versioning, and packaging complexity.

## 3. Central Scraper Registry

**Choice:** Keep enabled scraper factories in one registry and resolve sources
by canonical name.

**Why:** New sources can be enabled without changing route or orchestration
logic. Cached factories also allow a scraper instance to retain its shared
rate limiter.

**Other options:**

- Hard-coded source checks in routes: simpler initially, but tightly coupled.
- Dependency-injection container: useful in a larger application, but excessive
  for the current number of services.
- Configuration-based dynamic loading: flexible, but harder to validate and
  debug.

## 4. Live Synchronous Search

**Choice:** `POST /jobs/scrape` performs a live multi-source scrape and returns
the results in the same request.

**Why:** Results are fresh and the MVP does not need queues, worker status,
polling, or a complete persistent job catalogue.

**Other options:**

- Scheduled ingestion: makes user searches fast and reduces repeated source
  traffic, but results can be stale and storage lifecycle becomes necessary.
- Asynchronous on-demand jobs with SQS: supports longer work and controlled
  retries, but needs job status and polling or streaming.
- Hybrid search: serve stored results immediately and offer a live refresh. This
  is likely the best long-term option once usage grows.

## 5. Bounded Source Concurrency

**Choice:** Scrape different job sources concurrently with a bounded
`ThreadPoolExecutor`.

**Why:** Total latency approaches the duration of the slowest source instead of
the sum of all source durations, while the worker limit prevents unbounded
resource use.

**Other options:**

- Sequential sources: easiest and gentlest on resources, but slow.
- Async I/O with `httpx`: more efficient at high concurrency, but requires an
  async request path and larger refactor.
- Queue workers per source: stronger scaling and isolation, but adds distributed
  infrastructure.

## 6. Bounded Page Concurrency

**Choice:** Paginated scrapers fetch pages concurrently, capped by the smaller
of the configured worker count and requested page count.

**Why:** Page requests are I/O-bound, so threads reduce waiting time without
creating idle or unlimited workers. Results are restored to page order for
deterministic output.

**Other options:**

- Sequential pages: simpler but substantially slower.
- Async page requests: scales to more simultaneous requests with fewer threads,
  but increases implementation complexity.
- One global executor: enforces a hard application-wide limit, but lets large
  sources monopolize workers and couples scraper internals to orchestration.

**Scaling note:** Nested source and page pools can produce approximately
`source_workers * page_workers` active tasks. A future global workload limit may
be needed.

## 7. Threads for Network-Bound Work

**Choice:** Use Python threads rather than processes or a fully async stack.

**Why:** Scraping spends most time waiting for network responses. Threads offer
a small implementation change over `requests` and are not significantly
limited by the GIL for I/O-bound work.

**Other options:**

- Process pools: useful for CPU-heavy transformations, but expensive for HTTP
  waiting.
- `asyncio`: better for very high connection counts, but requires async-aware
  libraries and call chains.
- Scrapy: provides mature crawling and throttling, but is a larger framework
  than the MVP currently needs.

## 8. Shared Defensive HTTP Client

**Choice:** Centralize sessions, headers, connect/read timeouts, retry policy,
backoff, `Retry-After` support, status validation, and cleanup.

**Why:** All scrapers receive consistent network behavior. Sessions reuse
connections, timeouts prevent indefinite waits, and GET retries recover from
temporary failures safely.

**Other options:**

- Raw `requests.get` calls: less code, but duplicate policies and poor failure
  consistency.
- `httpx`: offers sync and async APIs, but does not provide enough benefit until
  an async migration is desired.
- Browser automation: necessary for JavaScript-only sites, but much slower and
  more memory-intensive.

## 9. Per-Scraper Request Rate Limiting

**Choice:** Share a thread-safe rate limiter across clients belonging to the
same cached scraper.

**Why:** Workers can overlap response waiting and parsing while request starts
remain spaced, reducing bursts and pressure on source websites.

**Other options:**

- Semaphore only: limits concurrent requests but not requests per second.
- Token bucket: permits controlled bursts and is more flexible.
- Redis-backed distributed limiter: coordinates all Lambda instances, but adds
  infrastructure and network latency.
- Per-source SQS workers: control total consumption through worker concurrency.

**Limitation:** The current limiter is process-local. Concurrent Lambda
instances each enforce their own independent limit.

## 10. Lazy Job Detail Loading

**Choice:** Return lightweight jobs.ch summaries during search and fetch the
full detail only when a user selects an incomplete result. Complete RSS jobs
skip this request.

**Why:** It dramatically reduces requests, source load, Lambda duration, and
initial response latency. If 100 results are returned and four are opened, only
four detail pages are fetched instead of 100.

**Other options:**

- Eager details: complete data immediately, but slow and request-heavy.
- Background prefetch of nearby jobs: faster browsing, but can fetch unused
  details.
- Persistent detail cache: makes repeat views fast, but requires freshness and
  expiry rules.

## 11. RSS When a Structured Feed Exists

**Choice:** Fetch SwissDevJobs through one public RSS request, parse all entries,
and filter locally.

**Why:** One structured request is cheaper, faster, and less fragile than
scraping multiple presentation pages.

**Other options:**

- HTML scraping: may expose more fields, but is more brittle and request-heavy.
- Official API: preferable when available and permitted.
- Browser automation: only justified when content cannot be obtained through a
  feed, API, or normal HTTP response.

## 12. Structured Data Before HTML Fallbacks

**Choice:** Parse embedded application JSON for jobs.ch listings and schema.org
`JobPosting` JSON-LD for details, falling back to HTML when needed.

**Why:** Structured data is usually easier to validate and less coupled to page
layout than presentation HTML.

**Other options:**

- CSS-selector-only parsing: easy to start, but breaks when page layout changes.
- Headless browser DOM extraction: handles rendered content, but costs more
  memory, time, and infrastructure.
- Private/internal APIs: efficient but potentially unstable or unsuitable from
  a compliance perspective.

## 13. Normalized Canonical Job Model

**Choice:** Convert every source result into one Pydantic `NormalizedJob`
contract, with an optional raw payload escape hatch.

**Why:** Validation happens at the scraper boundary and all downstream systems
can consume the same shape.

**Other options:**

- Preserve only raw payloads: maximizes fidelity, but every consumer needs an
  adapter.
- Store only canonical fields: simplest, but may discard useful source-specific
  information.
- Separate source event schemas: strong fidelity and versioning, but increases
  downstream transformation work.

## 14. Deterministic Extraction Before AI

**Choice:** Normalize locations and extract seniority, languages, and remote
type with multilingual rules.

**Why:** Rules are fast, inexpensive, reproducible, testable, and do not depend
on an AI provider.

**Other options:**

- LLM extraction for every job: handles nuance, but adds latency, cost, and
  nondeterminism.
- Classical NLP model: predictable runtime with better semantic coverage, but
  requires training or model maintenance.
- Rules with LLM fallback: the recommended future approach for ambiguous cases.

## 15. Two-Level Deduplication

**Choice:** Deduplicate within a source by canonical URL and across sources by a
normalized `(title, company, location)` fingerprint.

**Why:** Set-based matching is approximately O(n), inexpensive, and
conservative. Jobs missing identity fields are retained to avoid false merges.

**Other options:**

- URL-only: exact and cheap, but cannot match the same vacancy across boards.
- Fuzzy text matching: detects wording variations, but costs more CPU and needs
  tuned thresholds.
- Embedding similarity: detects semantic duplication, but adds model cost and
  can merge merely similar roles.
- Persistent canonical vacancy graph: strongest for analytics, but requires
  confidence, merge, and correction workflows.

## 16. Stable Content-Derived Job IDs

**Choice:** Derive job IDs from source identity and canonical source URL.

**Why:** IDs remain stable across repeated live searches and are available
without first writing jobs to a database.

**Other options:**

- Random UUIDs: easy, but the same job receives a new ID on every search.
- Database-generated IDs: stable after persistence, but forces every result to
  be stored.
- Source external IDs: efficient, but only unique within one source and may not
  exist everywhere.

## 17. Partial Failure Instead of All-or-Nothing Search

**Choice:** Preserve successful pages and sources. Return `partial` when some
sources fail and HTTP 502 only when every source fails.

**Why:** One changed or unavailable website should not prevent users from
receiving jobs from healthy sources.

**Other options:**

- Fail-fast: simpler semantics, but reduces availability.
- Silently ignore failures: cleaner responses, but hides operational problems.
- Async retry after the response: improves completeness, but requires stored
  search state or streaming updates.

## 18. Persist Interactions, Not Every Live Result

**Choice:** Search results are transient. DynamoDB stores a full job snapshot
only after the user stars it or marks it as applied.

**Why:** Storage and write traffic scale with meaningful user actions rather
than total scrape volume. Stored jobs remain readable even if the source later
removes them.

**Other options:**

- Persist every scraped job: enables history, analytics, and reusable AI
  enrichment, but adds writes, expiry, freshness, and stronger deduplication.
- Persist URL references only: very small records, but tracked jobs depend on
  the external source remaining available.
- Shared canonical jobs plus user references: best for many users, but requires
  reliable canonical identity and additional reads.

## 19. Full Snapshot in Each Interaction

**Choice:** A user interaction contains the normalized job snapshot alongside
`starred`, `applied`, and timestamps.

**Why:** A single DynamoDB query can render tracked jobs without joins, batch
lookups, or live source requests.

**Other options:**

- Normalize jobs into shared records: reduces duplication, but needs a second
  batch read and record lifecycle management.
- Event-only interaction history: preserves every transition, but requires
  projection logic to obtain current state.

## 20. Monotonic Applied State

**Choice:** Once a job is marked applied, later star changes do not clear the
applied flag or timestamp. Records with neither state are deleted.

**Why:** It prevents accidental loss of application history while keeping the
table sparse.

**Other options:**

- Fully reversible applied state: flexible, but easier to clear accidentally.
- Append-only application events: auditable, but more complex to query.
- Separate application entity: preferable once applications have stages,
  documents, interviews, and notes.

## 21. DynamoDB Single-Table Keys

**Choice:** Use generic `PK` and `SK` keys, currently
`USER#<id>` / `JOB#<id>` for interactions.

**Why:** All interactions for one user are retrieved with a partition query,
and future item types can share the table through key prefixes.

**Other options:**

- Separate DynamoDB tables per entity: easier to understand, but creates more
  infrastructure and cross-entity operations.
- PostgreSQL: stronger joins, constraints, and analytics, but requires database
  operation and scaling decisions.
- DynamoDB plus OpenSearch: strong operational access and full-text search, but
  duplicates data and requires synchronization.

## 22. DynamoDB On-Demand Billing

**Choice:** Use `PAY_PER_REQUEST`, server-side encryption, and point-in-time
recovery.

**Why:** MVP traffic is unpredictable, so on-demand billing avoids capacity
planning. Encryption and recovery provide basic data protection.

**Other options:**

- Provisioned capacity with autoscaling: can be cheaper at stable, sustained
  traffic, but requires tuning.
- Reserved relational database: useful for relational workloads, but incurs
  baseline cost even when idle.

## 23. Browser `localStorage` Search Cache

**Choice:** Save the latest query and results in the browser and restore them
after refresh.

**Why:** Refreshes do not repeat external scraping, and no server-side cache
infrastructure is required.

**Other options:**

- Memory-only state: simplest, but lost on refresh.
- IndexedDB: supports larger structured caches, but has a more complex API.
- DynamoDB result cache: shareable and durable, but adds read/write cost and TTL
  management.
- Redis: fast shared caching with expiry, but adds baseline infrastructure cost.

**Limitation:** Browser results can become stale, are not shared across devices,
and currently have no expiry or schema version.

## 24. Custom React Hook as UI Controller

**Choice:** Keep search, selection, lazy details, caching, interactions, and
loading states in `useJobsDashboard`, while components remain presentational.

**Why:** It centralizes the current single-page workflow without adding a state
management dependency.

**Other options:**

- State distributed among components: less initial abstraction, but harder to
  coordinate.
- React Context or Zustand: useful for state shared across many routes.
- TanStack Query: stronger server-state caching, invalidation, and request
  deduplication; likely useful as the frontend grows.

## 25. REST and Source-Neutral Endpoints

**Choice:** Provide unified search, generic source detail, and interaction REST
endpoints.

**Why:** The API is easy to consume and does not expose one endpoint per job
board.

**Other options:**

- GraphQL: flexible field selection, but adds resolver and schema complexity.
- Server-Sent Events: can stream source results as they finish and improve
  perceived latency.
- WebSockets: suitable for long-running interactive jobs, but unnecessary for
  the current request-response workflow.

## 26. Static Next.js Frontend

**Choice:** Build a client-driven Next.js frontend for static export to S3 and
CloudFront.

**Why:** Static assets are inexpensive, globally cacheable, and require no
always-running Node.js server.

**Other options:**

- Next.js server-side rendering: better for SEO and public job pages, but needs
  a server runtime.
- Vite React SPA: simpler for a purely client-side dashboard, but provides fewer
  built-in paths toward future server rendering.
- FastAPI templates: one deployment unit, but less suitable for the planned rich
  React interface.

## 27. FastAPI on AWS Lambda Through Mangum

**Choice:** Adapt the FastAPI ASGI application to Lambda with Mangum.

**Why:** It scales to zero, has little operational overhead, and keeps local
FastAPI development conventional.

**Other options:**

- ECS/Fargate: better for long-running or browser-heavy scrapers.
- EC2: can be cheaper under consistently high utilization, but needs server
  management.
- Lambda plus SQS workers: a good future split between the API and slow scraping
  work.
- AWS Batch: appropriate for large scheduled ingestion batches.

**Limitation:** Synchronous scraping consumes billable Lambda time while waiting
and is constrained by execution duration, memory, and process-local rate limits.

## 28. Separate Static Frontend and API Deployments

**Choice:** Deploy frontend assets independently from backend Lambda code.

**Why:** Each side can release only when its files change, uses a deployment
method appropriate to its runtime, and has separate AWS permissions.

**Other options:**

- One container serving API and frontend: simple artifact, but prevents static
  CDN hosting and couples releases.
- Full Next.js server deployment: integrates frontend and backend-for-frontend
  logic, but adds a persistent/serverless Node runtime.

## 29. Terraform as Infrastructure Source of Truth

**Choice:** Provision Lambda, DynamoDB, IAM, frontend bucket access controls, and
deployment roles with Terraform, while CI updates application artifacts.
CloudFront and its OAC remain console-managed.

**Why:** Infrastructure is reviewable and reproducible, while code-only releases
remain fast.

**Other options:**

- AWS CDK: uses a programming language and reusable constructs, but adds build
  and synthesis layers.
- Serverless Framework or SAM: convenient for Lambda-centric applications, but
  introduces another deployment abstraction.
- Managing CloudFront in Terraform: reproducible, but unnecessary for the slim
  deployment stack while the existing distribution remains console-managed.

## 30. GitHub Actions OIDC and Least-Privilege Roles

**Choice:** Let GitHub Actions assume separate, repository-and-branch-scoped AWS
roles using short-lived OIDC credentials.

**Why:** No long-lived AWS keys are stored in GitHub. Backend and frontend roles
receive only their required deployment permissions.

**Other options:**

- Stored IAM access keys: simpler setup, but creates long-lived secret rotation
  and leakage risk.
- One shared deployment administrator role: convenient, but violates least
  privilege and increases blast radius.

## 31. Mocked and Deterministic Tests

**Choice:** Test parsers, retries, concurrency, routes, and failure behavior
without live network dependencies.

**Why:** Tests remain fast, repeatable, CI-friendly, and do not create unwanted
traffic to job boards.

**Other options:**

- Live end-to-end tests: detect real site changes, but are slow and flaky and
  may violate source expectations if run frequently.
- Recorded HTTP fixtures: realistic and deterministic, but must be refreshed
  and may contain large or sensitive payloads.
- Periodic synthetic monitoring: complements unit tests by detecting production
  source changes outside the main CI suite.

## 32. Current Choice Versus Likely Long-Term Architecture

The current system optimizes for low MVP complexity and low idle cost. As usage
and AI processing grow, the likely progression is:

1. Add a short-lived shared cache for identical searches.
2. Move slow or Playwright-based sources into bounded queue workers.
3. Schedule recurring ingestion for frequently requested sources.
4. Store canonical shared jobs and lightweight per-user references.
5. Apply deterministic filters before AI processing.
6. Queue AI scoring and enrichment only for relevant jobs.
7. Add distributed per-source rate limits and production authentication.

These changes should be introduced in response to measured traffic, latency,
cost, or reliability problems rather than preemptively replacing the simpler
MVP design.

## 33. Reuse the JobCloud Scraper Strategy for jobup.ch

**Choice:** Implement jobup.ch as a thin `JobsChScraper` subclass and make the
JobCloud listing and detail paths configurable on the parent class.

**Why:** Live inspection confirmed that jobup.ch uses the same embedded
`__INIT__` listing shape and schema.org `JobPosting` detail format as jobs.ch.
Only the host and URL paths differ today, so inheritance keeps validation,
normalization, concurrency, rate limiting, and lazy details consistent without
duplicating a large parser.

**Other options:**

- Duplicate a complete jobup.ch scraper: isolates future site divergence, but
  immediately duplicates parsing and network behavior that are currently equal.
- Extract a new abstract JobCloud base class: gives the cleanest conceptual
  hierarchy, but adds a larger refactor before a second behavior has diverged.
- Parse visual HTML cards: works with the server-rendered page, but is more
  coupled to presentation changes than the existing structured payload.
- Use Playwright: unnecessary because listings and JSON-LD details are already
  present in ordinary HTTP responses, while adding runtime and deployment cost.

**Limitation:** The shared undocumented payload can change, and either JobCloud
site may diverge independently. Parser validation raises a source failure rather
than reporting an untrustworthy empty result; the subclass can override a parser
later if jobup.ch develops a different structure.

## 34. Central Switzerland-Only Filter

**Choice:** Keep only normalized jobs whose source-provided `country_code` is
exactly `CH` in the existing scrape orchestration step.

**Why:** One small central check guarantees the API does not return foreign or
unclassified jobs and keeps the rule out of the route and frontend.

**Other options:** Filtering separately inside every scraper would duplicate
the same policy and make new sources easier to implement inconsistently.
