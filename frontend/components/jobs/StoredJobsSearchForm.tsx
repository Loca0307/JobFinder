"use client";

type Props = {
  term: string;
  location: string;
  isLoading: boolean;
  onTermChange: (value: string) => void;
  onLocationChange: (value: string) => void;
  onSubmit: () => void;
};

export function StoredJobsSearchForm(props: Props) {
  return (
    <form
      className="mb-5 grid items-end gap-4 rounded-xl border border-slate-200 bg-white p-5 lg:grid-cols-[minmax(220px,.8fr)_minmax(240px,1fr)_minmax(190px,.75fr)_auto]"
      aria-label="Search stored jobs"
      onSubmit={(event) => {
        event.preventDefault();
        void props.onSubmit();
      }}
    >
      <div>
        <p className="mb-1 text-xs font-extrabold uppercase text-teal-700">Database search</p>
        <h2 className="text-xl font-bold">Search stored jobs</h2>
        <p className="mt-1 text-sm text-slate-500">This searches DynamoDB and never starts the scraper.</p>
      </div>
      <label className="grid gap-2 text-sm font-bold text-slate-600">
        Keywords
        <input
          value={props.term}
          onChange={(event) => props.onTermChange(event.target.value)}
          placeholder="Title, company, skill"
          className="min-h-12 rounded-lg border border-slate-200 bg-slate-50 px-4 text-slate-900 outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
        />
      </label>
      <label className="grid gap-2 text-sm font-bold text-slate-600">
        Location
        <input
          value={props.location}
          onChange={(event) => props.onLocationChange(event.target.value)}
          placeholder="Stored job location"
          className="min-h-12 rounded-lg border border-slate-200 bg-slate-50 px-4 text-slate-900 outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
        />
      </label>
      <button
        type="submit"
        disabled={props.isLoading}
        className="min-h-12 rounded-lg border border-slate-300 bg-white px-5 font-bold text-slate-800 transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60"
      >
        {props.isLoading ? "Searching…" : "Search database"}
      </button>
    </form>
  );
}
