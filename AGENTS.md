# AGENTS.md

## Project Overview

This project is an agentic AI-powered job-search application focused
initially on Switzerland.

The system should:

1.  Scrape job offers from the main Swiss job websites.
2.  Store scraped job offers in DynamoDB for AWS/Lambda deployment.
3.  Later expand to scraping company/business career pages directly.
4.  Use AI to classify and score job offers based on each user's
    profile.
5.  Recommend the most relevant jobs to each user.
6.  Analyze every job against the user's current skills and identify
    missing qualifications.
7.  Recommend concrete actions (courses, certifications, portfolio
    projects, learning resources) that increase the user's suitability
    for a job.
8.  Provide a modern web GUI built with Next.js and React.

The long-term goal is to build an AI career agent that not only finds
jobs, but actively helps users become stronger candidates over time.

------------------------------------------------------------------------

## Tech Stack

Preferred stack:

-   Backend: Python
-   API: FastAPI
-   Database: DynamoDB
-   Scraping: BeautifulSoup, Requests, Playwright when needed
-   AI/LLM: Start with local Ollama if possible, later allow OpenAI or
    other providers
-   Frontend: Next.js with React and TypeScript
-   Migrations: Alembic
-   Package management:
    -   Backend: uv or pip
    -   Frontend: npm
-   Deployment: Docker / Docker Compose

------------------------------------------------------------------------

## Main Architecture

``` text
backend/
  app/
    api/
    core/
    db/
    models/
    schemas/
    services/
    scrapers/
    ai/
    jobs/
    users/

frontend/
  app/
  components/
  lib/
  types/

docker-compose.yml
README.md
AGENTS.md
```

------------------------------------------------------------------------

## Side work

# Important command:
Every time a complete new feature gets implemented, update the ARCHITECTURE.md file with a new section with the feature name as the title and some bullet points and short text describing how the feature got implemented. A bit more deeply, explain the flow in the project that the feature follow, especially the file it uses. If the implmenentation of a feature gets changed, also update its section. Also at the top of the file keep a list of "tech stack" used in the project, these are meant also libraries specific for some tasks.

-------------------------------------------------------------------------

## Core Features

### 1. Job Scraping

The first version should scrape the major Swiss job websites.

Initial target sources:

-   SwissDevJobs
-   jobs.ch
-   jobup.ch
-   Indeed Switzerland
-   Company career pages (later)
-   LinkedIn only if feasible and compliant

Extract structured information:

-   title
-   company
-   location
-   description
-   requirements
-   seniority
-   employment type
-   remote type
-   salary
-   required languages
-   source website
-   source URL
-   apply URL
-   posting date
-   scrape timestamp

Each scraper must be independent and return normalized job objects.

------------------------------------------------------------------------

### 2. Company Career Page Scraping

After the main job-board scraping is stable, expand to company career
pages.

Goals:

-   Discover company websites
-   Detect career pages
-   Detect ATS platforms
-   Extract jobs directly from companies

Common career page paths:

-   /careers
-   /jobs
-   /join-us
-   /work-with-us
-   /karriere
-   /lavoro
-   /offerte-di-lavoro
-   /stellen

Future ATS support:

-   Greenhouse
-   Lever
-   Workday
-   Teamtailor
-   Personio
-   SmartRecruiters

------------------------------------------------------------------------

### 3. Database

Use DynamoDB.

Initial item types in the jobs table:

-   source items
-   job items
-   scrape run items
-   user items
-   user profile items
-   job score items
-   application items

Jobs should be deduplicated.

------------------------------------------------------------------------

### 4. User Profile

Allow users to configure:

-   studies
-   degree
-   university
-   experience
-   technical skills
-   preferred locations
-   languages
-   desired roles
-   remote preference
-   salary expectations
-   work permit
-   industries of interest
-   excluded roles

------------------------------------------------------------------------

### 5. AI Job Classification

The AI compares each job with the user profile.

Output example:

``` json
{
  "score": 85,
  "decision": "apply",
  "reason": "Strong match for backend Python roles.",
  "matched_skills": ["Python", "SQL", "FastAPI"],
  "missing_skills": ["AWS"],
  "confidence": 0.93
}
```

Use simple rule-based filtering before invoking the LLM whenever
possible.

------------------------------------------------------------------------

### 6. Skill Gap Analysis

For every job, compare:

-   required technologies
-   preferred technologies
-   education
-   certifications
-   experience
-   languages

against the user's profile.

Identify:

-   matched requirements
-   partially matched requirements
-   missing requirements

Example output:

``` json
{
  "overall_match": 82,
  "matched_skills": ["Python","SQL","Docker"],
  "missing_skills": ["AWS","Kubernetes"],
  "missing_certifications": ["AWS Cloud Practitioner"],
  "experience_gap": "1 additional year of backend development"
}
```

The AI should explain why requirements are missing.

------------------------------------------------------------------------

### 7. Career Improvement Agent

Include a second AI agent dedicated to career growth.

Instead of recommending jobs, it recommends actions that improve
employability.

Inputs:

-   user profile
-   desired jobs
-   market trends
-   missing skills

Outputs:

-   recommended courses
-   certifications
-   portfolio projects
-   books
-   YouTube playlists
-   official documentation
-   interview preparation
-   technologies to learn
-   soft skills

Recommendations should prioritize:

1.  Highest impact
2.  Lowest effort
3.  Lowest cost

------------------------------------------------------------------------

### 8. Learning Resource Recommendation

Recommend resources from:

-   Coursera
-   Udemy
-   edX
-   freeCodeCamp
-   YouTube
-   Official documentation

Each recommendation should include:

-   title
-   provider
-   estimated duration
-   cost
-   difficulty
-   direct link

------------------------------------------------------------------------

### 9. Frontend

Use Next.js + React + TypeScript.

Pages:

``` text
/dashboard
/jobs
/jobs/[id]
/profile
/applications
/learning
/settings
```

Job detail page should show:

-   AI match score
-   matched skills
-   missing skills
-   missing certifications
-   missing languages
-   experience gap
-   recommended learning path
-   recommended courses
-   suggested projects
-   suggested certifications
-   explanation of AI score

------------------------------------------------------------------------

## Development Principles

-   Modular architecture
-   Type-safe code
-   Async where appropriate
-   Separate scraping, AI and database logic
-   Log scraper failures
-   Never stop an entire scraping run because of one failing page

------------------------------------------------------------------------

## MVP

Success criteria:

-   User profile management
-   Scrape at least one Swiss job board
-   Save jobs to DynamoDB
-   Deduplicate jobs
-   AI job scoring
-   Skill-gap analysis
-   Personalized learning recommendations
-   Next.js frontend displaying recommendations
-   Users can mark jobs as Apply / Maybe / Reject

------------------------------------------------------------------------

## Future Features

-   CV parsing
-   Cover letter generation
-   Automatic application preparation
-   Browser automation
-   Salary analytics
-   Company insights
-   Skill trend analysis
-   Multi-user support

------------------------------------------------------------------------

## Environment Variables

``` text
DYNAMODB_JOBS_TABLE=
DYNAMODB_ENDPOINT_URL=
AWS_REGION=
OLLAMA_BASE_URL=
OLLAMA_MODEL=
OPENAI_API_KEY=
AI_PROVIDER=
SCRAPER_USER_AGENT=
```


-------------------------------------

## Codex instructions

1) 
When implementing features and most importantly during edits
at the code base implement the fixes as simply as possible if not specified, edit as less code as possible to fix the problems
 