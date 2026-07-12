import type { Job } from "@/types/job";

type Props = {
  jobs: Job[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

function valueOrFallback(value?: string | null) {
  return value?.trim() || "Not specified";
}

export function JobList({ jobs, selectedId, onSelect }: Props) {
  return (
    <div className="grid max-h-[calc(100vh-170px)] content-start gap-3 overflow-auto pr-1 max-lg:max-h-none" aria-label="Job results">
      {jobs.length === 0 ? (
        <p className="rounded-lg border border-slate-200 bg-white p-4 text-slate-500">Run a search to display jobs.</p>
      ) : null}
      {jobs.map((job) => (
        <button
          className={`grid w-full cursor-pointer gap-2 rounded-lg border bg-white p-4 text-left transition ${
            job.id === selectedId
              ? "border-teal-600 ring-3 ring-teal-100"
              : "border-slate-200 hover:border-slate-300 hover:shadow-sm"
          }`}
          key={job.id}
          type="button"
          onClick={() => onSelect(job.id)}
        >
          <span className="font-extrabold leading-snug">{job.title}</span>
          <span className="text-sm text-slate-500">
            {valueOrFallback(job.company)} · {valueOrFallback(job.location)}
          </span>
          <span className="flex flex-wrap gap-1.5">
            {job.employment_type ? <small className="rounded-full bg-slate-100 px-2 py-1 font-bold text-slate-600">{job.employment_type}</small> : null}
            {job.remote_type ? <small className="rounded-full bg-slate-100 px-2 py-1 font-bold text-slate-600">{job.remote_type}</small> : null}
            {job.source_website ? <small className="rounded-full bg-slate-100 px-2 py-1 font-bold text-slate-600">{job.source_website}</small> : null}
          </span>
        </button>
      ))}
    </div>
  );
}
