"use client";

import { JobDetails } from "@/components/jobs/JobDetails";
import { JobList } from "@/components/jobs/JobList";
import { ScrapeSearchForm } from "@/components/jobs/ScrapeSearchForm";
import { useJobsDashboard } from "@/hooks/useJobsDashboard";

export default function Home() {
  const dashboard = useJobsDashboard();

  return (
    <main className="mx-auto max-w-[1440px] p-5 lg:p-7">
      <header className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="mb-1 text-xs font-extrabold uppercase text-teal-700">JobFinder</p>
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">Swiss jobs</h1>
        </div>
        <div className="flex gap-2">
          <div className="min-w-24 rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <span className="block text-xl font-extrabold">🔍 {dashboard.jobsFoundCount}</span>
            <small className="text-slate-500">jobs found</small>
          </div>
          <button
            type="button"
            onClick={dashboard.showStarredJobs}
            className="min-w-24 rounded-lg border border-slate-200 bg-white px-4 py-3 text-left shadow-sm hover:bg-slate-50"
          >
            <span className="block text-xl font-extrabold">★ {dashboard.starredJobCount}</span>
            <small className="text-slate-500">starred jobs</small>
          </button>
          <button
            type="button"
            onClick={dashboard.clearAllSearches}
            className="rounded-lg border border-slate-200 bg-white px-4 font-bold text-slate-700 shadow-sm transition hover:bg-slate-100"
          >
            Clear searches
          </button>
        </div>
      </header>

      <ScrapeSearchForm
        term={dashboard.scrapeTerm}
        location={dashboard.scrapeLocation}
        isLoading={dashboard.isScraping}
        onTermChange={dashboard.setScrapeTerm}
        onLocationChange={dashboard.setScrapeLocation}
        onSubmit={dashboard.searchJobs}
      />

      {dashboard.lastRun ? (
        <p className="mt-3 rounded-lg bg-teal-50 px-4 py-3 text-sm font-medium text-teal-800" role="status">
          Live search complete: {dashboard.lastRun.jobs_found} jobs found.
        </p>
      ) : null}

      {dashboard.showingStarred ? (
        <p className="mb-5 rounded-lg bg-slate-100 px-4 py-3 text-sm font-medium text-slate-700">Showing starred jobs.</p>
      ) : null}

      {dashboard.error ? (
        <p className="my-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">{dashboard.error}</p>
      ) : null}

      <section className="grid min-h-[640px] gap-5 lg:grid-cols-[minmax(320px,430px)_minmax(0,1fr)]">
        <JobList
          jobs={dashboard.jobs}
          selectedId={dashboard.selectedJob?.id ?? null}
          onSelect={dashboard.setSelectedId}
        />
        <JobDetails
          job={dashboard.selectedJob}
          interaction={dashboard.selectedJob ? dashboard.interactions[dashboard.selectedJob.id] : undefined}
          isSaving={dashboard.savingJobId === dashboard.selectedJob?.id}
          onToggleStar={dashboard.toggleStar}
          onMarkApplied={dashboard.markApplied}
        />
      </section>
    </main>
  );
}
