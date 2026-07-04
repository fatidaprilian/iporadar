"use client";

import React, { useState, useEffect } from "react";
import { CandidateTable } from "@/components/CandidateTable";
import { AnalysisPanel } from "@/components/AnalysisPanel";
import { NavBar } from "@/components/NavBar";
import { api, IpoCandidate, AnalysisResult } from "@/lib/api";
import { Loader2, Play, TrendingUp, Clock, BarChart3, Zap } from "lucide-react";

export default function Dashboard() {
  const [candidates, setCandidates] = useState<IpoCandidate[]>([]);
  const [results, setResults] = useState<AnalysisResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const c = await api.getCandidates({ limit: 50 }).catch(() => ({ data: [] }));
        const r = await api.getLatestResults(1, 5).catch(() => ({ data: [] }));
        setCandidates(c.data || []);
        setResults(r.data || []);
      } catch (err) {
        console.error("Error fetching data", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleTriggerAnalysis = async () => {
    setAnalyzing(true);
    try {
      const { jobId } = await api.triggerAnalysis(5);

      const poll = async () => {
        for (let i = 0; i < 30; i++) {
          await new Promise((r) => setTimeout(r, 1000));
          const status = await api.getAnalysisStatus(jobId);
          if (status.status === "completed" || status.status === "failed") {
            break;
          }
        }
        const r = await api.getLatestResults(1, 5).catch(() => ({ data: [] }));
        setResults(r.data || []);
        setAnalyzing(false);
      };
      poll();
    } catch (err) {
      console.error("Error triggering analysis", err);
      setAnalyzing(false);
    }
  };

  const latestResult = results.length > 0 ? results[0] : null;
  const upcomingCount = candidates.filter((c) => c.status === "upcoming").length;
  const listedCount = candidates.filter((c) => c.status === "listed").length;

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
          <button
            onClick={handleTriggerAnalysis}
            disabled={analyzing || loading || candidates.length === 0}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium text-sm hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {analyzing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4 fill-current" />
            )}
            {analyzing ? "Analyzing..." : "Run Analysis"}
          </button>
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

        <main className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-150">
          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Active Candidates</h2>
            <div className="flex-1 bg-card rounded-xl border border-border overflow-hidden">
              {loading ? (
                <div className="flex items-center justify-center h-48">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <CandidateTable candidates={candidates} compact />
              )}
            </div>
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Latest Generation</h2>
            <div className="flex-1 flex flex-col min-h-0">
              {loading ? (
                <div className="flex-1 bg-card rounded-xl border border-border flex items-center justify-center min-h-100">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <AnalysisPanel result={latestResult} />
              )}
            </div>
          </section>
        </main>
      </div>
    </>
  );
}
