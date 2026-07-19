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
  required_languages?: string[];
  source_website?: string | null;
  source_url?: string | null;
  apply_url?: string | null;
  posting_date?: string | null;
};

export type JobScrapeRequest = {
  search_term?: string;
  location?: string;
};

export type ScrapeRun = {
  status: string;
  jobs_found: number;
  jobs_created: number;
  jobs_updated: number;
  jobs: Job[];
  sources: Array<{
    source_id: string;
    status: string;
    jobs_found: number;
    jobs_created: number;
    jobs_updated: number;
    error_message?: string | null;
  }>;
};
