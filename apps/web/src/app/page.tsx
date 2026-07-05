"use client";

import React, { useState, useEffect } from "react";
import { CandidateTable } from "@/components/CandidateTable";
import { AnalysisPanel } from "@/components/AnalysisPanel";
import { NavBar } from "@/components/NavBar";
import { api, IpoCandidate, AnalysisResult } from "@/lib/api";
import { Loader2, TrendingUp, Clock, BarChart3, Zap, RefreshCw } from "lucide-react";

export default function Dashboard() {
  const [candidates, setCandidates] = useState<IpoCandidate[]>([]);
  const [results, setResults] = useState<AnalysisResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzingUpcoming, setAnalyzingUpcoming] = useState(false);
  const [analyzingListed, setAnalyzingListed] = useState(false);

  const refreshResults = async () => {
    const r = await api.getLatestResults(1, 10).catch(() => ({ data: [] }));
    setResults(r.data || []);
  };

  const refreshCandidates = async () => {
    const c = await api.getCandidates({ limit: 50 }).catch(() => ({ data: [] }));
    setCandidates(c.data || []);
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        await Promise.all([refreshCandidates(), refreshResults()]);
      } catch (err) {
        console.error("Error fetching data", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleAnalyzeUpcoming = async () => {
    setAnalyzingUpcoming(true);
    try {
      await api.triggerPipeline("upcoming");

      const pollPipeline = async () => {
        for (let i = 0; i < 120; i++) {
          await new Promise((r) => setTimeout(r, 2000));
          const status = await api.getScraperStatus();
          if (status.active === 0) break;
        }
        await Promise.all([refreshCandidates(), refreshResults()]);
        setAnalyzingUpcoming(false);
      };
      pollPipeline();
    } catch (err) {
      console.error("Error analyzing upcoming", err);
      setAnalyzingUpcoming(false);
    }
  };

  const handleAnalyzeListed = async () => {
    setAnalyzingListed(true);
    try {
      await api.triggerPipeline("listed");

      const pollPipeline = async () => {
        for (let i = 0; i < 60; i++) {
          await new Promise((r) => setTimeout(r, 1000));
          const status = await api.getScraperStatus();
          if (status.active === 0) break;
        }
        await refreshResults();
        setAnalyzingListed(false);
      };
      pollPipeline();
    } catch (err) {
      console.error("Error analyzing listed", err);
      setAnalyzingListed(false);
    }
  };

  const upcomingResult = results.find((r) => r.prompt.includes("Mode: LIVE"));
  const listedResult = results.find((r) => r.prompt.includes("Mode: LISTED"));
  const upcomingCount = candidates.filter((c) => c.status === "upcoming").length;
  const listedCount = candidates.filter((c) => c.status === "listed").length;
  const isBusy = analyzingUpcoming || analyzingListed;

  const stats = [
    { label: "Total Candidates", value: candidates.length, icon: BarChart3 },
    { label: "Upcoming IPOs", value: upcomingCount, icon: Clock },
    { label: "Listed", value: listedCount, icon: TrendingUp },
    { label: "Analysis Runs", value: results.length, icon: Zap },
  ];

  return (
    <>
      <NavBar />
      <div className="flex-1 flex flex-col p-6 max-w-7xl mx-auto w-full gap-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Dashboard</h1>
            <p className="text-muted-foreground mt-1 text-sm">
              IPO screening & ML-powered analysis
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleAnalyzeUpcoming}
              disabled={isBusy || loading || upcomingCount === 0}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg font-medium text-sm hover:bg-emerald-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {analyzingUpcoming ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              {analyzingUpcoming ? "Scraping & Analyzing..." : "Analisa Upcoming"}
            </button>
            <button
              onClick={handleAnalyzeListed}
              disabled={isBusy || loading || listedCount === 0}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg font-medium text-sm hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {analyzingListed ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <TrendingUp className="w-4 h-4" />
              )}
              {analyzingListed ? "Analyzing..." : "Analisa Listed"}
            </button>
          </div>
        </header>

        {!loading && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {stats.map((s) => (
              <div
                key={s.label}
                className="bg-card rounded-lg border border-border px-4 py-3 flex items-center gap-3"
              >
                <s.icon className="w-4 h-4 text-muted-foreground" />
                <div>
                  <p className="text-xl font-bold text-foreground">{s.value}</p>
                  <p className="text-xs text-muted-foreground">{s.label}</p>
                </div>
              </div>
            ))}
          </div>
        )}

        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Upcoming Candidates</h2>
          <div className="bg-card rounded-xl border border-border overflow-hidden">
            {loading ? (
              <div className="flex items-center justify-center h-48">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <CandidateTable candidates={candidates.filter(c => c.status === "upcoming")} compact />
            )}
          </div>
        </section>

        <main className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-120">
          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Analisa Upcoming (LIVE)</h2>
            <div className="flex-1 flex flex-col min-h-0">
              {loading ? (
                <div className="flex-1 bg-card rounded-xl border border-border flex items-center justify-center min-h-80">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : analyzingUpcoming ? (
                <div className="flex-1 bg-card rounded-xl border border-border flex flex-col items-center justify-center min-h-80 gap-3">
                  <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
                  <p className="text-sm text-muted-foreground">Scraping live data & generating prompt...</p>
                </div>
              ) : (
                <AnalysisPanel result={upcomingResult || null} />
              )}
            </div>
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Analisa Listed (Strategi)</h2>
            <div className="flex-1 flex flex-col min-h-0">
              {loading ? (
                <div className="flex-1 bg-card rounded-xl border border-border flex items-center justify-center min-h-80">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : analyzingListed ? (
                <div className="flex-1 bg-card rounded-xl border border-border flex flex-col items-center justify-center min-h-80 gap-3">
                  <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                  <p className="text-sm text-muted-foreground">Generating listed analysis prompt...</p>
                </div>
              ) : (
                <AnalysisPanel result={listedResult || null} />
              )}
            </div>
          </section>
        </main>
      </div>
    </>
  );
}
