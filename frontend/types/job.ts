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
};
