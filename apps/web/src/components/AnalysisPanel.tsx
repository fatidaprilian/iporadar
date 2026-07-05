"use client";

import React, { useState } from "react";
import { AnalysisResult } from "@/lib/api";
import { Copy, CheckCircle2, FileText } from "lucide-react";
import { format } from "date-fns";

export function AnalysisPanel({ result }: { result: AnalysisResult | null }) {
  const [copied, setCopied] = useState(false);

  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center p-12 rounded-xl bg-card border border-dashed border-border text-muted-foreground h-full min-h-100">
        <FileText className="w-8 h-8 text-muted-foreground/30 mb-3" />
        <p className="font-medium text-foreground">No Analysis Yet</p>
        <p className="text-sm mt-1 text-center max-w-sm">
          Click "Run Analysis" to generate a structured LLM prompt from candidate data.
        </p>
      </div>
    );
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(result.prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isListed = result.prompt.includes("Mode: LISTED");
  const isLive = result.prompt.includes("Mode: LIVE");

  const badgeLabel = isListed ? "Listed" : isLive ? "Live" : "Ready";
  const badgeClass = isListed
    ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
    : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400";

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm flex flex-col h-full max-h-200">
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div>
          <h3 className="font-semibold text-foreground flex items-center gap-2">
            LLM Analysis Prompt
            <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase ${badgeClass}`}>
              {badgeLabel}
            </span>
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Generated {format(new Date(result.created_at), "dd MMM yyyy HH:mm")}
            <span className="mx-1.5 opacity-30">|</span>
            {result.prompt.length.toLocaleString()} chars
          </p>
        </div>
        <button
          onClick={handleCopy}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
            copied
              ? "bg-emerald-600 text-white"
              : "bg-primary text-primary-foreground hover:bg-primary/90"
          }`}
        >
          {copied ? <CheckCircle2 className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
          {copied ? "Copied!" : "Copy Prompt"}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar bg-[#0d1117] text-[#c9d1d9] p-5 text-[13px] font-mono leading-relaxed">
        <pre className="whitespace-pre-wrap m-0">{result.prompt}</pre>
      </div>
    </div>
  );
}
