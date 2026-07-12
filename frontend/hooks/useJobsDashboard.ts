"use client";

import { useMemo, useState } from "react";
import { fetchJobs, scrapeJobsCh } from "@/lib/jobs";
import type { Job, ScrapeRun } from "@/types/job";

export function useJobsDashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [scrapeTerm, setScrapeTerm] = useState("");
  const [scrapeLocation, setScrapeLocation] = useState("");
  const [storedTerm, setStoredTerm] = useState("");
  const [storedLocation, setStoredLocation] = useState("");
  const [isScraping, setIsScraping] = useState(false);
  const [isSearchingStored, setIsSearchingStored] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<ScrapeRun | null>(null);

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedId) ?? jobs[0] ?? null,
    [jobs, selectedId]
  );

  function showJobs(nextJobs: Job[]) {
    setJobs(nextJobs);
    setSelectedId(nextJobs[0]?.id ?? null);
  }

  async function searchJobsCh() {
    setIsScraping(true);
    setError(null);
    try {
      const run = await scrapeJobsCh({
        search_term: scrapeTerm.trim() || undefined,
        location: scrapeLocation.trim() || undefined
      });
      setLastRun(run);
      showJobs(run.jobs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "jobs.ch search failed");
    } finally {
      setIsScraping(false);
    }
  }

  async function searchStoredJobs() {
    setIsSearchingStored(true);
    setError(null);
    try {
      const matches = await fetchJobs(100, storedTerm, storedLocation);
      setLastRun(null);
      showJobs(matches);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stored job search failed");
    } finally {
      setIsSearchingStored(false);
    }
  }

  return {
    jobs,
    selectedJob,
    selectedId,
    setSelectedId,
    scrapeTerm,
    setScrapeTerm,
    scrapeLocation,
    setScrapeLocation,
    storedTerm,
    setStoredTerm,
    storedLocation,
    setStoredLocation,
    isScraping,
    isSearchingStored,
    error,
    lastRun,
    searchJobsCh,
    searchStoredJobs
  };
}
