"use client";

import React from "react";
import { IpoCandidate } from "@/lib/api";
import { format } from "date-fns";

export function CandidateTable({ candidates }: { candidates: IpoCandidate[] }) {
  if (!candidates || candidates.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 border border-dashed border-border rounded-xl bg-card text-card-foreground">
        <p className="text-muted-foreground mb-2">No IPO candidates found.</p>
        <p className="text-sm">Make sure the scraper has run recently.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border shadow-sm">
      <table className="w-full text-sm text-left">
        <thead className="text-xs uppercase bg-muted text-muted-foreground border-b border-border">
          <tr>
            <th className="px-6 py-4 font-medium">Ticker</th>
            <th className="px-6 py-4 font-medium">Company</th>
            <th className="px-6 py-4 font-medium">Sector</th>
            <th className="px-6 py-4 font-medium">Listing Date</th>
            <th className="px-6 py-4 font-medium text-right">Offer Price</th>
            <th className="px-6 py-4 font-medium">Underwriter</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-card">
          {candidates.map((c) => (
            <tr key={c.id} className="hover:bg-muted/50 transition-colors">
              <td className="px-6 py-4 font-bold text-primary">{c.ticker}</td>
              <td className="px-6 py-4 font-medium">{c.company_name}</td>
              <td className="px-6 py-4 text-muted-foreground">{c.sector}</td>
              <td className="px-6 py-4 whitespace-nowrap">
                {c.listing_date ? format(new Date(c.listing_date), "dd MMM yyyy") : "TBA"}
              </td>
              <td className="px-6 py-4 text-right font-mono">
                {c.offer_price_idr ? `Rp ${c.offer_price_idr.toLocaleString("id-ID")}` : "TBA"}
              </td>
              <td className="px-6 py-4">
                <div className="flex items-center gap-2">
                  <span className="truncate max-w-[150px]" title={c.underwriter || ""}>
                    {c.underwriter || "-"}
                  </span>
                  {c.underwriter_tier && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-accent text-accent-foreground">
                      T{c.underwriter_tier}
                    </span>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
