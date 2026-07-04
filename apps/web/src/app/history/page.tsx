"use client";

import React, { useState, useEffect } from "react";
import { NavBar } from "@/components/NavBar";
import { api, AnalysisResult } from "@/lib/api";
import { Loader2, FileText, ChevronRight, Clock } from "lucide-react";
import { format } from "date-fns";
import Link from "next/link";

export default function HistoryPage() {
  const [results, setResults] = useState<AnalysisResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    const fetchResults = async () => {
      setLoading(true);
      try {
        const res = await api.getLatestResults(page, 10);
        setResults(res.data || []);
        setTotalPages(res.meta?.totalPages || 1);
      } catch (err) {
        console.error("Failed to fetch results", err);
      } finally {
        setLoading(false);
      }
    };
    fetchResults();
  }, [page]);

  return (
    <>
      <NavBar />
      <div className="flex-1 flex flex-col p-6 max-w-7xl mx-auto w-full gap-6">
        <header>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Analysis History</h1>
          <p className="text-muted-foreground mt-1">
            Browse past analysis runs and their generated prompts
          </p>
        </header>

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : results.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-16 border border-dashed border-border rounded-xl bg-card text-muted-foreground">
            <Clock className="w-12 h-12 mb-3 opacity-30" />
            <p className="font-medium text-foreground">No analysis results yet</p>
            <p className="text-sm mt-1">Run an analysis from the Dashboard to get started.</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {results.map((result) => (
              <Link
                key={result.id}
                href={`/history/${result.id}`}
                className="group bg-card rounded-xl border border-border p-5 shadow-sm hover:border-primary/50 hover:shadow-md transition-all"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                      <FileText className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground">
                        Analysis — {format(new Date(result.created_at), "dd MMM yyyy, HH:mm")}
                      </h3>
                      <p className="text-sm text-muted-foreground mt-0.5">
                        {result.candidate_count} candidates analyzed
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {result.top_candidates && result.top_candidates.length > 0 && (
                      <div className="hidden sm:flex items-center gap-2">
                        {result.top_candidates.slice(0, 3).map((tc, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-bold bg-muted text-foreground"
                          >
                            #{tc.compositeRank} {tc.ticker}
                          </span>
                        ))}
                        {result.top_candidates.length > 3 && (
                          <span className="text-xs text-muted-foreground">
                            +{result.top_candidates.length - 3} more
                          </span>
                        )}
                      </div>
                    )}
                    <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Page {page} of {totalPages}</span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 bg-card border border-border rounded-md hover:bg-muted disabled:opacity-50 text-foreground"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 bg-card border border-border rounded-md hover:bg-muted disabled:opacity-50 text-foreground"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
