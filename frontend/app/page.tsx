"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchJobs } from "@/lib/jobs";
import type { Job } from "@/types/job";

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
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const locations = useMemo(() => {
    const uniqueLocations = new Set(
      jobs.map((job) => job.location?.trim()).filter((value): value is string => Boolean(value))
    );
    return Array.from(uniqueLocations).sort();
  }, [jobs]);

  const filteredJobs = useMemo(() => {
    const searchTerm = query.trim().toLowerCase();
    return jobs.filter((job) => {
      const matchesQuery =
        !searchTerm ||
        [job.title, job.company, job.location, job.description, job.seniority]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(searchTerm);
      const matchesLocation = !location || job.location === location;
      return matchesQuery && matchesLocation;
    });
  }, [jobs, location, query]);

  const selectedJob =
    filteredJobs.find((job) => job.id === selectedId) ?? filteredJobs[0] ?? jobs[0] ?? null;

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
          <button type="button" onClick={() => void loadJobs()} disabled={isLoading}>
            {isLoading ? "Loading" : "Refresh"}
          </button>
        </div>
      </section>

      <section className="filters" aria-label="Job filters">
        <label>
          Search
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Role, company, skill"
          />
        </label>
        <label>
          Location
          <select value={location} onChange={(event) => setLocation(event.target.value)}>
            <option value="">All locations</option>
            {locations.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </section>

      {error ? <p className="notice error">{error}</p> : null}

      <section className="workspace">
        <div className="jobList" aria-label="Stored jobs">
          {isLoading && jobs.length === 0 ? <p className="notice">Loading jobs...</p> : null}
          {!isLoading && filteredJobs.length === 0 ? (
            <p className="notice">No jobs match the current filters.</p>
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
