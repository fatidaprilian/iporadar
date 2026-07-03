"use client";

import React, { useState } from "react";
import { AnalysisResult } from "@/lib/api";
import { Copy, CheckCircle2 } from "lucide-react";
import { format } from "date-fns";

export function AnalysisPanel({ result }: { result: AnalysisResult | null }) {
  const [copied, setCopied] = useState(false);

  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center p-12 border border-dashed border-border rounded-xl bg-card text-muted-foreground">
        <div className="w-16 h-16 mb-4 rounded-full bg-muted flex items-center justify-center">
          <svg className="w-8 h-8 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        </div>
        <p className="font-medium text-foreground">No Analysis Results Yet</p>
        <p className="text-sm mt-1 text-center max-w-md">
          Trigger a new analysis to generate a copy-paste ready LLM prompt containing all candidate data and fundamental scores.
        </p>
      </div>
    );
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(result.prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm flex flex-col h-full max-h-[800px]">
      <div className="flex items-center justify-between p-4 border-b border-border bg-muted/30">
        <div>
          <h3 className="font-semibold text-foreground flex items-center gap-2">
            LLM Analysis Prompt
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase bg-primary text-primary-foreground">
              Ready
            </span>
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Generated {format(new Date(result.created_at), "dd MMM yyyy HH:mm")}
          </p>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium text-sm hover:bg-primary/90 transition-colors shadow-sm"
        >
          {copied ? <CheckCircle2 className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
          {copied ? "Copied!" : "Copy Prompt"}
        </button>
      </div>
      
      <div className="p-0 flex-1 overflow-y-auto bg-[#1e1e1e] text-[#d4d4d4] p-4 text-sm font-mono leading-relaxed custom-scrollbar">
        <pre className="whitespace-pre-wrap font-inherit m-0">
          {result.prompt}
        </pre>
      </div>
    </div>
  );
}
