import type { Job, JobInteraction, JobScrapeRequest, ScrapeResult } from "@/types/job";

const API_BASE_URL = process.env.NODE_ENV === "production" ? "" : "http://localhost:8000";

export async function scrapeJobs(request: JobScrapeRequest): Promise<ScrapeResult> {
  const response = await fetch(`${API_BASE_URL}/jobs/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(
      typeof payload?.detail === "string"
        ? payload.detail
        : `Job search failed (${response.status})`
    );
  }

  return response.json() as Promise<ScrapeResult>;
}

export async function fetchJobDetail(sourceId: string, externalId: string): Promise<Job> {
  const response = await fetch(
    `${API_BASE_URL}/jobs/details/${encodeURIComponent(sourceId)}/${encodeURIComponent(externalId)}`
  );
  if (!response.ok) throw new Error(`Failed to load job details (${response.status})`);
  return response.json() as Promise<Job>;
}

export async function fetchJobInteractions(): Promise<JobInteraction[]> {
  const response = await fetch(`${API_BASE_URL}/jobs/interactions`);
  if (!response.ok) throw new Error(`Failed to load tracked jobs (${response.status})`);
  return response.json() as Promise<JobInteraction[]>;
}

export async function saveJobInteraction(
  job: Job,
  starred: boolean,
  applied: boolean
): Promise<JobInteraction | null> {
  const response = await fetch(
    `${API_BASE_URL}/jobs/interactions/${encodeURIComponent(job.id)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job, starred, applied })
    }
  );
  if (!response.ok) throw new Error(`Failed to update tracked job (${response.status})`);
  return response.json() as Promise<JobInteraction | null>;
}
