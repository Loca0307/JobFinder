import type { Job, JobScrapeRequest, ScrapeRun } from "@/types/job";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function fetchJobs(limit = 50): Promise<Job[]> {
  const response = await fetch(`${API_BASE_URL}/jobs?limit=${limit}`);

  if (!response.ok) {
    throw new Error(`Failed to load jobs (${response.status})`);
  }

  return response.json() as Promise<Job[]>;
}

export async function scrapeJobsCh(request: JobScrapeRequest): Promise<ScrapeRun> {
  const response = await fetch(`${API_BASE_URL}/jobs/scrape/jobs-ch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `jobs.ch search failed (${response.status})`);
  }

  return response.json() as Promise<ScrapeRun>;
}
