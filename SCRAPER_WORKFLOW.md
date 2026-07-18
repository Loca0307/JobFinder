# Job Scraper Request and Response Workflow

```mermaid
flowchart TD
    START(["API or service calls scraper.scrape()"])

    subgraph SCRAPER["1 · Scraper coordination"]
        START --> INPUT["Parameters<br/>search_term · location · pages=5"]
        INPUT --> CHECK{"pages ≥ 1?"}
        CHECK -- "No" --> EMPTY["Return empty job list"]
        CHECK -- "Yes" --> POOL["PaginatedJobScraper creates<br/>ThreadPoolExecutor"]
        POOL --> WORKERS["max_workers = min<br/>(SCRAPER_MAX_WORKERS, pages)"]
    end

    subgraph THREADS["2 · Concurrent page workers"]
        WORKERS --> W1["_scrape_page(..., page=1)"]
        WORKERS --> W2["_scrape_page(..., page=2)"]
        WORKERS --> W3["_scrape_page(..., page=3)"]
        WORKERS --> WN["_scrape_page(..., page=4–5)"]
        W1 --> URL1["Build listing URL"]
        W2 --> URL2["Build listing URL"]
        W3 --> URL3["Build listing URL"]
        WN --> URLN["Build listing URL"]
    end

    subgraph CLIENTS["3 · Independent clients and sessions"]
        URL1 --> C1["ScraperHttpClient 1<br/>requests.Session 1"]
        URL2 --> C2["ScraperHttpClient 2<br/>requests.Session 2"]
        URL3 --> C3["ScraperHttpClient 3<br/>requests.Session 3"]
        URLN --> CN["ScraperHttpClient 4–5<br/>independent sessions"]
    end

    subgraph LIMITER["4 · Shared source-wide rate limiter"]
        C1 --> RL["RequestRateLimiter.wait()"]
        C2 --> RL
        C3 --> RL
        CN --> RL
        RL --> LOCK["Acquire thread lock"]
        LOCK --> SLOT["Reserve next available<br/>request-start time"]
        SLOT --> WAIT{"Delay required?"}
        WAIT -- "Yes" --> SLEEP["Wait until reserved time"]
        WAIT -- "No" --> SEND
        SLEEP --> SEND["Call session.get()"]
    end

    subgraph HTTP["5 · Session, adapter and retry policy"]
        SEND --> SESSION["requests.Session<br/>adds shared headers"]
        SESSION --> HEADERS["User-Agent<br/>Accept-Language"]
        HEADERS --> ADAPTER["HTTPAdapter"]
        ADAPTER --> TIMEOUTS["Apply connect and read timeouts"]
        TIMEOUTS --> NETWORK["Send HTTPS GET request"]
    end

    subgraph WEBSITE["6 · Website processing"]
        NETWORK --> SITE["jobs.ch receives request"]
        SITE --> RESPONSE{"HTTP response"}
    end

    subgraph RETRIES["7 · Adapter response handling"]
        RESPONSE -- "429 / 500 / 502 / 503 / 504" --> RETRY{"Retries remaining?"}
        RETRY -- "Yes" --> BACKOFF["Wait using exponential backoff<br/>or Retry-After header"]
        BACKOFF --> NETWORK
        RETRY -- "No" --> HTTPERROR["raise_for_status()<br/>raises RequestException"]
        RESPONSE -- "Other 4xx error" --> HTTPERROR
        RESPONSE -- "Successful 2xx response" --> HTML["Return requests.Response"]
    end

    subgraph PARSING["8 · Listing and detail processing"]
        HTML --> LISTING["Parse listing HTML"]
        LISTING --> LINKS["Extract and deduplicate<br/>job-detail URLs"]
        LINKS --> EACH{"For each detail URL"}
        EACH --> DETAILGET["client.get(detail_url)"]
        DETAILGET --> RL
        HTML --> DETAILCHECK{"Listing or detail response?"}
        DETAILCHECK -- "Detail" --> JSONLD["Look for JobPosting JSON-LD"]
        JSONLD --> HASJSON{"Valid JSON-LD?"}
        HASJSON -- "Yes" --> NORMALIZEJSON["Normalize structured fields"]
        HASJSON -- "No" --> FALLBACK["Parse HTML fallback"]
        FALLBACK --> NORMALIZEHTML["Normalize available fields"]
        NORMALIZEJSON --> JOB["Create NormalizedJob"]
        NORMALIZEHTML --> JOB
        JOB --> MORE{"More detail URLs?"}
        MORE -- "Yes" --> EACH
        MORE -- "No" --> PAGE["Return page number<br/>and page jobs"]
    end

    subgraph ERRORS["9 · Failure isolation"]
        HTTPERROR --> REQUESTTYPE{"Failed request type"}
        REQUESTTYPE -- "Listing page" --> EMPTYPAGE["Return this page with no jobs"]
        REQUESTTYPE -- "Job detail" --> SKIP["Log failure and skip this job"]
        SKIP --> MORE
        W1 -. "Unexpected worker failure" .-> FAILEDWORKER["Log exception<br/>preserve other workers"]
        W2 -. "Unexpected worker failure" .-> FAILEDWORKER
        W3 -. "Unexpected worker failure" .-> FAILEDWORKER
        WN -. "Unexpected worker failure" .-> FAILEDWORKER
    end

    subgraph MERGE["10 · Final result assembly"]
        PAGE --> RESULTS["Collect completed page results"]
        EMPTYPAGE --> RESULTS
        FAILEDWORKER --> RESULTS
        RESULTS --> ORDER["Sort results by page number"]
        ORDER --> DEDUP["Deduplicate jobs by source_url"]
        DEDUP --> FINAL(["Return list[NormalizedJob]"])
    end
```

## Component ownership

| Component | File | Responsibility |
|---|---|---|
| `BaseJobScraper` | `backend/api/scrapers/base.py` | Defines the common scraper contract |
| `PaginatedJobScraper` | `backend/api/scrapers/base.py` | Thread pool, page coordination, failure isolation, and final merging |
| `JobsChScraper` | `backend/api/scrapers/jobs_ch.py` | jobs.ch URLs, listing parsing, detail parsing, and normalization |
| `RequestRateLimiter` | `backend/api/scrapers/http.py` | Coordinates request timing across every worker |
| `ScraperHttpClient` | `backend/api/scrapers/http.py` | Applies rate limiting and performs HTTP operations |
| `requests.Session` | Created inside `ScraperHttpClient` | Maintains headers and connections for one worker |
| `HTTPAdapter` | Mounted on each session | Connection pooling and automatic retries |
| `Retry` | Installed through the adapter | Status handling, exponential backoff, and `Retry-After` support |

Each thread owns an independent HTTP session, while every thread in the scraper
shares one rate limiter. This preserves safe concurrency while enforcing a single
source-wide request rate.
