"use client";

import React from "react";
import { IpoCandidate } from "@/lib/api";
import { format } from "date-fns";
import { TrendingUp, Clock } from "lucide-react";

export function CandidateTable({ candidates }: { candidates: IpoCandidate[] }) {
  if (!candidates || candidates.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <TrendingUp className="w-8 h-8 text-muted-foreground/30 mb-3" />
        <p className="text-muted-foreground text-sm">No IPO candidates found.</p>
        <p className="text-xs text-muted-foreground/70 mt-1">Run the scraper to fetch data.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto custom-scrollbar">
      <table className="w-full text-sm text-left">
        <thead>
          <tr className="text-xs uppercase text-muted-foreground border-b border-border">
            <th className="px-4 py-3 font-medium">Ticker</th>
            <th className="px-4 py-3 font-medium">Company</th>
            <th className="px-4 py-3 font-medium">Sector</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Listing Date</th>
            <th className="px-4 py-3 font-medium text-right">Offer Price</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/50">
          {candidates.map((c) => (
            <tr key={c.id} className="hover:bg-muted/30 transition-colors">
              <td className="px-4 py-3 font-bold text-primary">{c.ticker}</td>
              <td className="px-4 py-3 font-medium text-card-foreground max-w-48 truncate" title={c.company_name}>
                {c.company_name}
              </td>
              <td className="px-4 py-3 text-muted-foreground text-xs">{c.sector}</td>
              <td className="px-4 py-3">
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium ${
                  c.status === "upcoming"
                    ? "bg-blue-500/10 text-blue-500 dark:text-blue-400"
                    : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                }`}>
                  {c.status === "upcoming" ? (
                    <Clock className="w-3 h-3" />
                  ) : (
                    <TrendingUp className="w-3 h-3" />
                  )}
                  {c.status === "upcoming" ? "Upcoming" : "Listed"}
                </span>
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-muted-foreground">
                {c.listing_date ? format(new Date(c.listing_date), "dd MMM yyyy") : "TBA"}
              </td>
              <td className="px-4 py-3 text-right font-mono text-card-foreground">
                {c.offer_price_idr ? `Rp ${c.offer_price_idr.toLocaleString("id-ID")}` : "TBA"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
