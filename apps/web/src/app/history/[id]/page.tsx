"use client";

import React, { useState, useEffect } from "react";
import { NavBar } from "@/components/NavBar";
import { api, AnalysisResult } from "@/lib/api";
import { Loader2, Copy, CheckCircle2, ArrowLeft, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { format } from "date-fns";
import Link from "next/link";
import { useParams } from "next/navigation";

export default function ResultDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchResult = async () => {
      try {
        const r = await api.getResult(id);
        setResult(r);
      } catch (err) {
        setError("Failed to load analysis result");
      } finally {
        setLoading(false);
      }
    };
    fetchResult();
  }, [id]);

  const handleCopy = () => {
    if (!result) return;
    navigator.clipboard.writeText(result.prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getSentimentIcon = (score: string) => {
    const n = parseFloat(score);
    if (n > 0.1) return <TrendingUp className="w-4 h-4 text-green-500" />;
    if (n < -0.1) return <TrendingDown className="w-4 h-4 text-red-500" />;
    return <Minus className="w-4 h-4 text-muted-foreground" />;
  };

  return (
    <>
      <NavBar />
      <div className="flex-1 flex flex-col p-6 max-w-7xl mx-auto w-full gap-6">
        <Link
          href="/history"
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors w-fit"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to History
        </Link>

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : error || !result ? (
          <div className="flex flex-col items-center justify-center p-16 border border-dashed border-border rounded-xl bg-card text-muted-foreground">
            <p className="font-medium text-foreground">{error || "Result not found"}</p>
          </div>
        ) : (
          <>
            <header className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-foreground">
                  Analysis — {format(new Date(result.created_at), "dd MMM yyyy, HH:mm")}
                </h1>
                <p className="text-muted-foreground mt-1">
                  {result.candidate_count} candidates analyzed
                </p>
              </div>
              <button
                onClick={handleCopy}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium text-sm hover:bg-primary/90 transition-colors shadow-sm"
              >
                {copied ? <CheckCircle2 className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {copied ? "Copied!" : "Copy Prompt"}
              </button>
            </header>

            {/* Top Candidates Ranking */}
            {result.top_candidates && result.top_candidates.length > 0 && (
              <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
                <div className="px-5 py-3 border-b border-border bg-muted/30">
                  <h2 className="font-semibold text-foreground">Ranking</h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead className="text-xs uppercase bg-muted text-muted-foreground border-b border-border">
                      <tr>
                        <th className="px-5 py-3 font-medium">Rank</th>
                        <th className="px-5 py-3 font-medium">Ticker</th>
                        <th className="px-5 py-3 font-medium">Company</th>
                        <th className="px-5 py-3 font-medium text-right">L1 (First-day)</th>
                        <th className="px-5 py-3 font-medium text-right">L2 (30-day)</th>
                        <th className="px-5 py-3 font-medium text-right">Sentiment</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {result.top_candidates.map((tc) => (
                        <tr key={tc.compositeRank} className="hover:bg-muted/50 transition-colors">
                          <td className="px-5 py-3">
                            <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${
                              tc.compositeRank === 1
                                ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300"
                                : tc.compositeRank === 2
                                ? "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                                : tc.compositeRank === 3
                                ? "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300"
                                : "bg-muted text-muted-foreground"
                            }`}>
                              {tc.compositeRank}
                            </span>
                          </td>
                          <td className="px-5 py-3 font-bold text-primary">{tc.ticker}</td>
                          <td className="px-5 py-3 font-medium">{tc.companyName}</td>
                          <td className="px-5 py-3 text-right font-mono">
                            {(parseFloat(tc.layer1Score) * 100).toFixed(1)}%
                          </td>
                          <td className="px-5 py-3 text-right font-mono">
                            {(parseFloat(tc.layer2Score) * 100).toFixed(1)}%
                          </td>
                          <td className="px-5 py-3 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              {getSentimentIcon(tc.sentimentScore)}
                              <span className="font-mono">{parseFloat(tc.sentimentScore).toFixed(2)}</span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Prompt */}
            <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm flex flex-col">
              <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/30">
                <h2 className="font-semibold text-foreground flex items-center gap-2">
                  Generated Prompt
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase bg-primary text-primary-foreground">
                    Ready
                  </span>
                </h2>
                <span className="text-xs text-muted-foreground">
                  {result.prompt.length.toLocaleString()} characters
                </span>
              </div>
              <div className="bg-[#1e1e1e] text-[#d4d4d4] p-5 text-sm font-mono leading-relaxed max-h-[600px] overflow-y-auto">
                <pre className="whitespace-pre-wrap m-0">{result.prompt}</pre>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
