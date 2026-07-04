"use client";

import React, { useState, useEffect, useCallback } from "react";
import { NavBar } from "@/components/NavBar";
import { api, IpoCandidate } from "@/lib/api";
import { Loader2, Search, Filter, RefreshCw } from "lucide-react";
import { format } from "date-fns";

const SECTORS = [
  "All", "Banking", "Mining", "Technology", "Consumer Goods",
  "Property", "Infrastructure", "Healthcare", "Energy", "Telecommunications",
];

const STATUSES = [
  { value: "", label: "All Status" },
  { value: "upcoming", label: "Upcoming" },
  { value: "listed", label: "Listed" },
];

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState<IpoCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [scraping, setScraping] = useState(false);

  const fetchCandidates = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getCandidates({
        status: status || undefined,
        sector: sector || undefined,
        page,
        limit: 20,
      });
      setCandidates(res.data || []);
      setTotalPages(res.meta?.totalPages || 1);
      setTotal(res.meta?.total || 0);
    } catch (err) {
      console.error("Failed to fetch candidates", err);
    } finally {
      setLoading(false);
    }
  }, [status, sector, page]);

  useEffect(() => {
    fetchCandidates();
  }, [fetchCandidates]);

  const handleScrape = async () => {
    setScraping(true);
    try {
      await api.triggerScraper(["eipo"]);
      await new Promise((r) => setTimeout(r, 3000));
      await fetchCandidates();
    } catch (err) {
      console.error("Scraper failed", err);
    } finally {
      setScraping(false);
    }
  };

  const filtered = search
    ? candidates.filter(
        (c) =>
          c.ticker.toLowerCase().includes(search.toLowerCase()) ||
          c.company_name.toLowerCase().includes(search.toLowerCase())
      )
    : candidates;

  return (
    <>
      <NavBar />
      <div className="flex-1 flex flex-col p-6 max-w-7xl mx-auto w-full gap-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">Candidates</h1>
            <p className="text-muted-foreground mt-1">
              {total} IPO candidates in database
            </p>
          </div>
          <button
            onClick={handleScrape}
            disabled={scraping}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium text-sm hover:bg-primary/90 transition-colors disabled:opacity-50 shadow-sm"
          >
            <RefreshCw className={`w-4 h-4 ${scraping ? "animate-spin" : ""}`} />
            {scraping ? "Scraping..." : "Scrape e-IPO"}
          </button>
        </header>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-48 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search ticker or company..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-card border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            className="px-3 py-2 bg-card border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <select
            value={sector}
            onChange={(e) => { setSector(e.target.value === "All" ? "" : e.target.value); setPage(1); }}
            className="px-3 py-2 bg-card border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            {SECTORS.map((s) => (
              <option key={s} value={s === "All" ? "" : s}>{s}</option>
            ))}
          </select>
        </div>

        {/* Table */}
        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 text-muted-foreground">
              <Filter className="w-12 h-12 mb-3 opacity-30" />
              <p className="font-medium">No candidates found</p>
              <p className="text-sm mt-1">Try adjusting your filters or run the scraper.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs uppercase bg-muted text-muted-foreground border-b border-border">
                  <tr>
                    <th className="px-4 py-3 font-medium">Ticker</th>
                    <th className="px-4 py-3 font-medium">Company</th>
                    <th className="px-4 py-3 font-medium">Sector</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Listing Date</th>
                    <th className="px-4 py-3 font-medium text-right">Offer Price</th>
                    <th className="px-4 py-3 font-medium">Underwriter</th>
                    <th className="px-4 py-3 font-medium text-right">P/E</th>
                    <th className="px-4 py-3 font-medium text-right">P/B</th>
                    <th className="px-4 py-3 font-medium text-right">ROE</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {filtered.map((c) => (
                    <tr key={c.id} className="hover:bg-muted/50 transition-colors">
                      <td className="px-4 py-3 font-bold text-primary">{c.ticker}</td>
                      <td className="px-4 py-3 font-medium max-w-48 truncate" title={c.company_name}>
                        {c.company_name}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{c.sector}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          c.status === "upcoming"
                            ? "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
                            : c.status === "listed"
                            ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                            : "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300"
                        }`}>
                          {c.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {c.listing_date ? format(new Date(c.listing_date), "dd MMM yyyy") : "TBA"}
                      </td>
                      <td className="px-4 py-3 text-right font-mono">
                        {c.offer_price_idr ? `Rp ${c.offer_price_idr.toLocaleString("id-ID")}` : "-"}
                      </td>
                      <td className="px-4 py-3 truncate max-w-32" title={c.underwriter || ""}>
                        {c.underwriter || "-"}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-muted-foreground">
                        {c.fundamental?.pe_ratio != null ? Number(c.fundamental.pe_ratio).toFixed(1) : "-"}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-muted-foreground">
                        {c.fundamental?.pb_ratio != null ? Number(c.fundamental.pb_ratio).toFixed(1) : "-"}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-muted-foreground">
                        {c.fundamental?.roe != null ? `${(Number(c.fundamental.roe) * 100).toFixed(1)}%` : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pagination */}
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
