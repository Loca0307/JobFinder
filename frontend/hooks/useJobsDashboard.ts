"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchJobInteractions, saveJobInteraction, scrapeJobs } from "@/lib/jobs";
import type { Job, JobInteraction, ScrapeResult } from "@/types/job";

const SEARCH_STORAGE_KEY = "jobfinder.live-search";

export function useJobsDashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [scrapeTerm, setScrapeTerm] = useState("");
  const [scrapeLocation, setScrapeLocation] = useState("");
  const [isScraping, setIsScraping] = useState(false);
  const [savingJobId, setSavingJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<ScrapeResult | null>(null);
  const [interactions, setInteractions] = useState<Record<string, JobInteraction>>({});
  const [showingTracked, setShowingTracked] = useState(false);
  const [searchStorageLoaded, setSearchStorageLoaded] = useState(false);

  async function refreshInteractions() {
    try {
      const tracked = await fetchJobInteractions();
      setInteractions(Object.fromEntries(tracked.map((interaction) => [interaction.job.id, interaction])));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tracked jobs");
    }
  }

  useEffect(() => {
    void refreshInteractions();
  }, []);

  useEffect(() => {
    const savedSearch = window.localStorage.getItem(SEARCH_STORAGE_KEY);
    if (savedSearch) {
      try {
        const parsed = JSON.parse(savedSearch) as { term?: string; location?: string };
        setScrapeTerm(parsed.term ?? "");
        setScrapeLocation(parsed.location ?? "");
      } catch {
        window.localStorage.removeItem(SEARCH_STORAGE_KEY);
      }
    }
    setSearchStorageLoaded(true);
  }, []);

  useEffect(() => {
    if (!searchStorageLoaded) return;
    window.localStorage.setItem(
      SEARCH_STORAGE_KEY,
      JSON.stringify({ term: scrapeTerm, location: scrapeLocation })
    );
  }, [scrapeTerm, scrapeLocation, searchStorageLoaded]);

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedId) ?? jobs[0] ?? null,
    [jobs, selectedId]
  );

  function showJobs(nextJobs: Job[]) {
    setJobs(nextJobs);
    setSelectedId(nextJobs[0]?.id ?? null);
  }

  function clearResults() {
    showJobs([]);
    setLastRun(null);
    setError(null);
  }

  function clearAllSearches() {
    window.localStorage.removeItem(SEARCH_STORAGE_KEY);
    setScrapeTerm("");
    setScrapeLocation("");
    setShowingTracked(false);
    clearResults();
  }

  async function searchJobs() {
    setIsScraping(true);
    setError(null);
    try {
      const run = await scrapeJobs({
        search_term: scrapeTerm.trim() || undefined,
        location: scrapeLocation.trim() || undefined
      });
      setLastRun(run);
      setShowingTracked(false);
      showJobs(run.jobs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Job search failed");
    } finally {
      setIsScraping(false);
    }
  }

  function showTrackedJobs() {
    setLastRun(null);
    setShowingTracked(true);
    showJobs(Object.values(interactions).map((interaction) => interaction.job));
  }

  async function updateInteraction(job: Job, starred: boolean, applied: boolean) {
    setSavingJobId(job.id);
    setError(null);
    try {
      const saved = await saveJobInteraction(job, starred, applied);
      setInteractions((current) => {
        const next = { ...current };
        if (saved) next[job.id] = saved;
        else delete next[job.id];
        return next;
      });
      if (showingTracked && !saved) {
        showJobs(jobs.filter((candidate) => candidate.id !== job.id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update tracked job");
    } finally {
      setSavingJobId(null);
    }
  }

  function toggleStar(job: Job) {
    const current = interactions[job.id];
    return updateInteraction(job, !current?.starred, current?.applied ?? false);
  }

  function markApplied(job: Job) {
    const current = interactions[job.id];
    return updateInteraction(job, current?.starred ?? false, true);
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
    isScraping,
    savingJobId,
    error,
    lastRun,
    interactions,
    trackedJobCount: Object.keys(interactions).length,
    showingTracked,
    searchJobs,
    showTrackedJobs,
    toggleStar,
    markApplied,
    clearAllSearches
  };
}
