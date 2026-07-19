export type Job = {
  id: string;
  title: string;
  company?: string | null;
  location?: string | null;
  description?: string | null;
  requirements?: string | null;
  seniority?: string | null;
  employment_type?: string | null;
  remote_type?: string | null;
  salary?: string | null;
  required_languages?: string[];
  source_website?: string | null;
  source_url?: string | null;
  apply_url?: string | null;
  posting_date?: string | null;
  scrape_timestamp?: string | null;
  external_id?: string | null;
  raw_payload?: Record<string, unknown> | null;
  details_loaded?: boolean;
};

export type JobScrapeRequest = {
  search_term?: string;
  location?: string;
};

export type ScrapeResult = {
  status: string;
  jobs_found: number;
  jobs: Job[];
  sources: Array<{
    source_id: string;
    status: string;
    jobs_found: number;
    error_message?: string | null;
  }>;
};

export type JobInteraction = {
  job: Job;
  starred: boolean;
  applied: boolean;
  applied_at?: string | null;
  created_at: string;
  updated_at: string;
};
