import type { Job, JobScrapeRequest, ScrapeRun } from "@/types/job";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function fetchJobCount(): Promise<number> {
  const response = await fetch(`${API_BASE_URL}/jobs/count`);
  if (!response.ok) throw new Error(`Failed to load job count (${response.status})`);
  const payload = (await response.json()) as { count: number };
  return payload.count;
}

export async function fetchJobs(limit = 50, query = "", location = ""): Promise<Job[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (query.trim()) params.set("query", query.trim());
  if (location.trim()) params.set("location", location.trim());
  const response = await fetch(`${API_BASE_URL}/jobs?${params.toString()}`);

  if (!response.ok) {
    throw new Error(`Failed to load jobs (${response.status})`);
  }

  return response.json() as Promise<Job[]>;
}

export async function scrapeJobs(request: JobScrapeRequest): Promise<ScrapeRun> {
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

  return response.json() as Promise<ScrapeRun>;
}
