"use client";

type Props = {
  term: string;
  location: string;
  isLoading: boolean;
  onTermChange: (value: string) => void;
  onLocationChange: (value: string) => void;
  onSubmit: () => void;
};

export function ScrapeSearchForm(props: Props) {
  return (
    <form
      className="my-6 grid items-end gap-4 rounded-xl border border-teal-200 bg-gradient-to-br from-teal-50 to-white p-5 lg:grid-cols-[minmax(190px,.65fr)_minmax(240px,1fr)_minmax(190px,.8fr)_auto]"
      aria-label="Search Swiss job boards"
      onSubmit={(event) => {
        event.preventDefault();
        void props.onSubmit();
      }}
    >
      <div>
        <p className="mb-1 text-xs font-extrabold uppercase text-teal-700">Swiss job search</p>
        <h2 className="text-xl font-bold">Search live jobs</h2>
        <p className="mt-1 text-sm text-slate-500">
          Search jobs.ch, jobup.ch, and SwissDevJobs without storing every result.
        </p>
      </div>
      <label className="grid gap-2 text-sm font-bold text-slate-600">
        Role or keywords
        <input
          value={props.term}
          onChange={(event) => props.onTermChange(event.target.value)}
          placeholder="e.g. Python developer"
          maxLength={255}
          className="min-h-12 rounded-lg border border-slate-200 bg-white px-4 text-slate-900 outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
        />
      </label>
      <label className="grid gap-2 text-sm font-bold text-slate-600">
        Location
        <input
          value={props.location}
          onChange={(event) => props.onLocationChange(event.target.value)}
          placeholder="e.g. Zürich"
          maxLength={255}
          className="min-h-12 rounded-lg border border-slate-200 bg-white px-4 text-slate-900 outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
        />
      </label>
      <button
        type="submit"
        disabled={props.isLoading}
        className="min-h-12 rounded-lg bg-teal-700 px-5 font-extrabold whitespace-nowrap text-white transition hover:bg-teal-800 disabled:cursor-wait disabled:opacity-60"
      >
        {props.isLoading ? "Scraping…" : "Search job boards"}
      </button>
    </form>
  );
}
