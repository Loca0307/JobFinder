# Job Scraper Workflow

This document shows the normal path from `scraper.scrape()` to jobs.ch and back.
The diagram emphasizes which component is responsible for each part of the work.

```mermaid
flowchart TD
    CALL(["scraper.scrape(search_term, location, pages=5)"])

    subgraph COORDINATOR["1 · PaginatedJobScraper — coordinates the run"]
        PLAN["Creates one task per page"]
        POOL["ThreadPoolExecutor runs page tasks concurrently"]
        COLLECT["Collects page results"]
        MERGE["Restores page order and removes duplicate source URLs"]
    end

    subgraph SOURCE["2 · JobsChScraper — understands jobs.ch"]
        PAGE["Builds the jobs.ch listing URL for one page"]
        LISTING["Parses the listing response and extracts detail URLs"]
        DETAIL["Requests each job-detail URL"]
        PARSE["Parses JSON-LD or the HTML fallback"]
        NORMALIZE["Creates NormalizedJob objects"]
    end

    subgraph TRANSPORT["3 · ScraperHttpClient — controls HTTP access"]
        GET["Receives get(url)"]
        LIMIT["Asks the shared RequestRateLimiter for a request slot"]
        EXECUTE["Calls its worker's requests.Session"]
        STATUS["Checks the final HTTP status and returns the response"]
    end

    subgraph RATE["RequestRateLimiter — controls speed across all workers"]
        SLOT["Uses a lock to reserve the next request start time"]
        WAIT["Waits when required<br/>Default: 2 requests per second"]
    end

    subgraph SESSION["4 · requests.Session — owns one worker's HTTP state"]
        HEADERS["Applies User-Agent and Accept-Language headers"]
        CONNECTIONS["Reuses that worker's network connections"]
        DISPATCH["Sends the request through the mounted HTTPAdapter"]
    end

    subgraph ADAPTER["5 · HTTPAdapter + Retry — handles transport reliability"]
        POLICY["Applies timeouts and retry policy"]
        RETRIES["Retries temporary failures with backoff or Retry-After"]
        SEND["Sends the HTTPS request"]
    end

    SITE["6 · jobs.ch — processes the request"]
    RESPONSE["HTTP response<br/>status · headers · HTML"]
    RETURN(["Return list of NormalizedJob objects"])

    CALL --> PLAN --> POOL --> PAGE
    PAGE -->|"listing URL"| GET
    GET --> LIMIT --> SLOT --> WAIT --> EXECUTE
    EXECUTE --> HEADERS --> CONNECTIONS --> DISPATCH
    DISPATCH --> POLICY --> RETRIES --> SEND
    SEND -->|"GET request"| SITE
    SITE --> RESPONSE

    RESPONSE -. "response travels back" .-> RETRIES
    RETRIES -.-> DISPATCH
    DISPATCH -.-> STATUS
    STATUS -. "listing response" .-> LISTING

    LISTING --> DETAIL
    DETAIL -->|"detail URL: same HTTP path"| GET
    STATUS -. "detail response" .-> PARSE
    PARSE --> NORMALIZE
    NORMALIZE --> COLLECT --> MERGE --> RETURN
```

## Responsibility boundaries

| Component | Responsible for | Not responsible for |
|---|---|---|
| `BaseJobScraper` | Defining the common `scrape()` contract | Threads, HTTP, or jobs.ch parsing |
| `PaginatedJobScraper` | Creating page tasks, running the thread pool, collecting, ordering, and deduplicating results | Website-specific URLs or HTML parsing |
| `JobsChScraper` | Building jobs.ch URLs, discovering detail links, parsing responses, and creating `NormalizedJob` objects | Generic thread coordination or retry implementation |
| `RequestRateLimiter` | Enforcing one request rate across every worker belonging to the scraper | Sending requests or interpreting responses |
| `ScraperHttpClient` | Connecting the rate limiter to the session and checking final HTTP errors | Understanding jobs.ch HTML |
| `requests.Session` | Keeping one worker's headers, cookies, and reusable connections | Coordinating other worker sessions |
| `HTTPAdapter` and `Retry` | Connection pooling, retries, backoff, and `Retry-After` handling | Page scheduling or job normalization |
| `jobs.ch` | Receiving the request and returning an HTTP response | Internal scraper behavior |

## Important ownership rule

```text
One JobsChScraper run
├── one shared RequestRateLimiter
├── one PaginatedJobScraper coordinator
└── multiple page workers
    ├── worker 1 → HTTP client 1 → Session 1 → HTTPAdapter
    ├── worker 2 → HTTP client 2 → Session 2 → HTTPAdapter
    └── worker N → HTTP client N → Session N → HTTPAdapter
```

Sessions are independent because each belongs to one worker. The limiter is shared
because it must control the combined request rate of all workers.

## Normal workflow in plain language

1. `PaginatedJobScraper.scrape()` creates five page tasks.
2. The thread pool starts those tasks concurrently.
3. Each task calls the jobs.ch-specific `_scrape_page()` method.
4. `JobsChScraper` builds a listing URL and asks its `ScraperHttpClient` to fetch it.
5. The client waits for the shared rate limiter before starting the request.
6. The worker's session applies headers and passes the request to its HTTP adapter.
7. The adapter sends the request and manages temporary retries.
8. jobs.ch returns an HTTP response through the same transport components.
9. `JobsChScraper` extracts job-detail URLs from the listing response.
10. Each detail URL follows the same client, limiter, session, and adapter path.
11. `JobsChScraper` parses each detail response into a `NormalizedJob`.
12. `PaginatedJobScraper` collects all page results, restores page order, removes
    duplicate source URLs, and returns the final job list.
