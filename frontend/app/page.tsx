"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchJobs, scrapeJobsCh } from "@/lib/jobs";
import type { FormEvent } from "react";
import type { Job, ScrapeRun } from "@/types/job";

function compactDate(value?: string | null) {
  if (!value) return "No date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "No date";
  return new Intl.DateTimeFormat("en", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  }).format(date);
}

function normalize(value?: string | null) {
  return value?.trim() || "Not specified";
}

export default function Home() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [filterQuery, setFilterQuery] = useState("");
  const [filterLocation, setFilterLocation] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isScraping, setIsScraping] = useState(false);
  const [scrapeError, setScrapeError] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<ScrapeRun | null>(null);

  async function loadJobs() {
    setIsLoading(true);
    setError(null);
    try {
      const nextJobs = await fetchJobs(100);
      setJobs(nextJobs);
      setSelectedId((current) => current ?? nextJobs[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load jobs");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadJobs();
  }, []);

  async function handleScrape(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsScraping(true);
    setScrapeError(null);
    setLastRun(null);

    try {
      const run = await scrapeJobsCh({
        search_term: query.trim() || undefined,
        location: location.trim() || undefined
      });
      setLastRun(run);
      await loadJobs();
    } catch (err) {
      setScrapeError(err instanceof Error ? err.message : "jobs.ch search failed");
    } finally {
      setIsScraping(false);
    }
  }

  const filteredJobs = useMemo(() => {
    const term = filterQuery.trim().toLowerCase();
    const place = filterLocation.trim().toLowerCase();

    return jobs.filter((job) => {
      const searchableText = [job.title, job.company, job.description, job.requirements]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      const matchesTerm = !term || searchableText.includes(term);
      const matchesLocation = !place || job.location?.toLowerCase().includes(place) === true;
      return matchesTerm && matchesLocation;
    });
  }, [filterLocation, filterQuery, jobs]);

  const selectedJob =
    filteredJobs.find((job) => job.id === selectedId) ?? filteredJobs[0] ?? null;

  useEffect(() => {
    if (filteredJobs.length > 0 && !filteredJobs.some((job) => job.id === selectedId)) {
      setSelectedId(filteredJobs[0].id);
    }
  }, [filteredJobs, selectedId]);

  return (
    <main className="shell">
      <section className="topbar" aria-label="Dashboard summary">
        <div>
          <p className="eyebrow">JobFinder</p>
          <h1>Swiss jobs</h1>
        </div>
        <div className="stats">
          <div>
            <span>{jobs.length}</span>
            <small>stored</small>
          </div>
          <div>
            <span>{filteredJobs.length}</span>
            <small>shown</small>
          </div>
          {lastRun ? (
            <div>
              <span>{lastRun.jobs_found}</span>
              <small>last scrape</small>
            </div>
          ) : null}
          <button type="button" onClick={() => void loadJobs()} disabled={isLoading}>
            {isLoading ? "Loading" : "Refresh"}
          </button>
        </div>
      </section>

      <form className="filters searchBar" aria-label="Search jobs.ch" onSubmit={handleScrape}>
        <div className="filterHeading">
          <p className="eyebrow">jobs.ch</p>
          <h2>Search new jobs</h2>
        </div>
        <label>
          Role or keywords
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. Python developer"
            maxLength={255}
          />
        </label>
        <label>
          Location
          <input
            value={location}
            onChange={(event) => setLocation(event.target.value)}
            placeholder="e.g. Zürich"
            maxLength={255}
          />
        </label>
        <button type="submit" disabled={isScraping}>
          {isScraping ? "Scraping jobs.ch…" : "Search jobs.ch"}
        </button>
        {scrapeError ? <p className="scrapeMessage error">{scrapeError}</p> : null}
        {lastRun ? (
          <p className="scrapeMessage success" role="status">
            Five-page scrape complete: {lastRun.jobs_found} found, {lastRun.jobs_created} new and{" "}
            {lastRun.jobs_updated} updated. Results have been refreshed below.
          </p>
        ) : null}
      </form>

      <section className="storedFilters" aria-label="Filter stored jobs">
        <div className="filterHeading">
          <p className="eyebrow">Local filter</p>
          <h2>Filter stored jobs</h2>
          <p>This only filters saved results. It does not start a scrape.</p>
        </div>
        <label>
          Keywords
          <input
            value={filterQuery}
            onChange={(event) => setFilterQuery(event.target.value)}
            placeholder="Title, company, skill"
          />
        </label>
        <label>
          Location
          <input
            value={filterLocation}
            onChange={(event) => setFilterLocation(event.target.value)}
            placeholder="Filter saved locations"
          />
        </label>
        <button
          type="button"
          onClick={() => {
            setFilterQuery("");
            setFilterLocation("");
          }}
          disabled={!filterQuery && !filterLocation}
        >
          Clear filters
        </button>
      </section>

      {error ? <p className="notice error">{error}</p> : null}

      <section className="workspace">
        <div className="jobList" aria-label="Stored jobs">
          {isLoading && jobs.length === 0 ? <p className="notice">Loading jobs...</p> : null}
          {!isLoading && filteredJobs.length === 0 ? (
            <p className="notice">
              {jobs.length === 0
                ? "No stored jobs yet. Start a jobs.ch scrape above."
                : "No stored jobs match these local filters."}
            </p>
          ) : null}
          {filteredJobs.map((job) => (
            <button
              className={job.id === selectedJob?.id ? "jobCard active" : "jobCard"}
              key={job.id}
              type="button"
              onClick={() => setSelectedId(job.id)}
            >
              <span className="jobTitle">{job.title}</span>
              <span className="jobMeta">
                {normalize(job.company)} · {normalize(job.location)}
              </span>
              <span className="jobTags">
                {job.employment_type ? <small>{job.employment_type}</small> : null}
                {job.remote_type ? <small>{job.remote_type}</small> : null}
                {job.source_website ? <small>{job.source_website}</small> : null}
              </span>
            </button>
          ))}
        </div>

        <article className="detail" aria-label="Selected job">
          {selectedJob ? (
            <>
              <div className="detailHeader">
                <div>
                  <p className="eyebrow">{normalize(selectedJob.source_website)}</p>
                  <h2>{selectedJob.title}</h2>
                  <p>
                    {normalize(selectedJob.company)} · {normalize(selectedJob.location)}
                  </p>
                </div>
                <div className="actions">
                  {selectedJob.source_url ? (
                    <a href={selectedJob.source_url} target="_blank" rel="noreferrer">
                      Source
                    </a>
                  ) : null}
                  {selectedJob.apply_url ? (
                    <a href={selectedJob.apply_url} target="_blank" rel="noreferrer">
                      Apply
                    </a>
                  ) : null}
                </div>
              </div>

              <dl className="facts">
                <div>
                  <dt>Posted</dt>
                  <dd>{compactDate(selectedJob.posting_date)}</dd>
                </div>
                <div>
                  <dt>Seniority</dt>
                  <dd>{normalize(selectedJob.seniority)}</dd>
                </div>
                <div>
                  <dt>Type</dt>
                  <dd>{normalize(selectedJob.employment_type)}</dd>
                </div>
                <div>
                  <dt>Remote</dt>
                  <dd>{normalize(selectedJob.remote_type)}</dd>
                </div>
                <div>
                  <dt>Salary</dt>
                  <dd>{normalize(selectedJob.salary)}</dd>
                </div>
                <div>
                  <dt>Languages</dt>
                  <dd>
                    {selectedJob.required_languages?.length
                      ? selectedJob.required_languages.join(", ")
                      : "Not specified"}
                  </dd>
                </div>
              </dl>

              <section className="description">
                <h3>Description</h3>
                <p>{normalize(selectedJob.description)}</p>
              </section>

              {selectedJob.requirements ? (
                <section className="description">
                  <h3>Requirements</h3>
                  <p>{selectedJob.requirements}</p>
                </section>
              ) : null}
            </>
          ) : (
            <p className="notice">No jobs loaded yet.</p>
          )}
        </article>
      </section>
    </main>
  );
}
