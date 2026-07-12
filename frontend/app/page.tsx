"use client";

import { JobDetails } from "@/components/jobs/JobDetails";
import { JobList } from "@/components/jobs/JobList";
import { ScrapeSearchForm } from "@/components/jobs/ScrapeSearchForm";
import { StoredJobsSearchForm } from "@/components/jobs/StoredJobsSearchForm";
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
            <span className="block text-xl font-extrabold">{dashboard.jobs.length}</span>
            <small className="text-slate-500">shown</small>
          </div>
          {dashboard.lastRun ? (
            <div className="min-w-24 rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <span className="block text-xl font-extrabold">{dashboard.lastRun.jobs_found}</span>
              <small className="text-slate-500">last scrape</small>
            </div>
          ) : null}
        </div>
      </header>

      <ScrapeSearchForm
        term={dashboard.scrapeTerm}
        location={dashboard.scrapeLocation}
        isLoading={dashboard.isScraping}
        onTermChange={dashboard.setScrapeTerm}
        onLocationChange={dashboard.setScrapeLocation}
        onSubmit={dashboard.searchJobsCh}
      />

      {dashboard.lastRun ? (
        <p className="mt-3 rounded-lg bg-teal-50 px-4 py-3 text-sm font-medium text-teal-800" role="status">
          Scrape complete: {dashboard.lastRun.jobs_found} found, {dashboard.lastRun.jobs_created} new and{" "}
          {dashboard.lastRun.jobs_updated} updated.
        </p>
      ) : null}

      <StoredJobsSearchForm
        term={dashboard.storedTerm}
        location={dashboard.storedLocation}
        isLoading={dashboard.isSearchingStored}
        onTermChange={dashboard.setStoredTerm}
        onLocationChange={dashboard.setStoredLocation}
        onSubmit={dashboard.searchStoredJobs}
      />

      {dashboard.error ? (
        <p className="my-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">{dashboard.error}</p>
      ) : null}

      <section className="grid min-h-[640px] gap-5 lg:grid-cols-[minmax(320px,430px)_minmax(0,1fr)]">
        <JobList
          jobs={dashboard.jobs}
          selectedId={dashboard.selectedJob?.id ?? null}
          onSelect={dashboard.setSelectedId}
        />
        <JobDetails job={dashboard.selectedJob} />
      </section>
    </main>
  );
}
