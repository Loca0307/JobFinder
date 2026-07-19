import type { Job, JobInteraction } from "@/types/job";

function valueOrFallback(value?: string | null) {
  return value?.trim() || "Not specified";
}

function formatDate(value?: string | null) {
  if (!value) return "No date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "No date";
  return new Intl.DateTimeFormat("en", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  }).format(date);
}

type Props = {
  job: Job | null;
  interaction?: JobInteraction;
  isSaving: boolean;
  isLoadingDetail: boolean;
  onToggleStar: (job: Job) => void;
  onMarkApplied: (job: Job) => void;
};

export function JobDetails({ job, interaction, isSaving, isLoadingDetail, onToggleStar, onMarkApplied }: Props) {
  return (
    <article className="min-w-0 rounded-xl border border-slate-200 bg-white p-6 shadow-sm" aria-label="Selected job">
      {!job ? <p className="rounded-lg border border-slate-200 p-4 text-slate-500">Select or search for a job.</p> : null}
      {job ? (
        <>
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="mb-1 text-xs font-extrabold uppercase text-teal-700">{valueOrFallback(job.source_website)}</p>
              <h2 className="text-2xl font-extrabold leading-tight sm:text-3xl">{job.title}</h2>
              <p className="mt-2 text-slate-500">{valueOrFallback(job.company)} · {valueOrFallback(job.location)}</p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={isSaving || isLoadingDetail || job.details_loaded === false}
                onClick={() => onToggleStar(job)}
                className="rounded-lg border border-slate-200 px-4 py-3 font-bold hover:bg-slate-50 disabled:opacity-50"
              >
                {interaction?.starred ? "★ Starred" : "☆ Star"}
              </button>
              {job.source_url ? <a className="rounded-lg border border-slate-200 px-4 py-3 font-bold hover:bg-slate-50" href={job.source_url} target="_blank" rel="noreferrer">Source</a> : null}
              {job.apply_url ? <a className="rounded-lg bg-teal-700 px-4 py-3 font-bold text-white hover:bg-teal-800" href={job.apply_url} target="_blank" rel="noreferrer">Apply</a> : null}
            </div>
          </div>
          <div className="mt-4 flex items-center gap-3">
            <button
              type="button"
              disabled={isSaving || isLoadingDetail || job.details_loaded === false || interaction?.applied}
              onClick={() => onMarkApplied(job)}
              className="rounded-lg border border-teal-700 px-4 py-2 font-bold text-teal-800 hover:bg-teal-50 disabled:cursor-default disabled:opacity-60"
            >
              {interaction?.applied ? "Applied ✓" : "Mark as applied"}
            </button>
            <span className="text-sm text-slate-500">Use this only after completing the external application.</span>
          </div>
          <dl className="my-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <Fact label="Posted" value={formatDate(job.posting_date)} />
            <Fact label="Seniority" value={valueOrFallback(job.seniority)} />
            <Fact label="Type" value={valueOrFallback(job.employment_type)} />
            <Fact label="Remote" value={valueOrFallback(job.remote_type)} />
            <Fact label="Languages" value={job.required_languages?.join(", ") || "Not specified"} />
          </dl>
          {isLoadingDetail ? <p className="mb-4 text-sm font-medium text-teal-700">Loading full job details…</p> : null}
          <TextSection title="Description" text={valueOrFallback(job.description)} />
          {job.requirements ? <TextSection title="Requirements" text={job.requirements} /> : null}
        </>
      ) : null}
    </article>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-h-20 rounded-lg bg-slate-100 p-3">
      <dt className="mb-1 text-xs font-extrabold uppercase text-slate-500">{label}</dt>
      <dd className="font-bold break-words">{value}</dd>
    </div>
  );
}

function TextSection({ title, text }: { title: string; text: string }) {
  return (
    <section className="border-t border-slate-200 py-5">
      <h3 className="mb-2 font-bold">{title}</h3>
      <p className="whitespace-pre-line leading-7 text-slate-700">{text}</p>
    </section>
  );
}
