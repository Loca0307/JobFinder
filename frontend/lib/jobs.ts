import type { Job } from "@/types/job";

const API_BASE_URL = "http://localhost:8000";

export async function fetchJobs(limit = 50): Promise<Job[]> {
  const response = await fetch(`${API_BASE_URL}/jobs`);

  if (!response.ok) {
    throw new Error(`Failed to load jobs (${response.status})`);
  }

  return response.json() as Promise<Job[]>;
}
