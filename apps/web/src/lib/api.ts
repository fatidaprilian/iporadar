export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface IpoCandidate {
  id: string;
  ticker: string;
  company_name: string;
  sector: string;
  listing_date: string;
  offer_price_idr: number;
  share_count: number | null;
  underwriter: string | null;
  underwriter_tier: number | null;
  status: string;
  fundamental?: {
    pe_ratio: number | null;
    pb_ratio: number | null;
    roe: number | null;
    debt_to_equity: number | null;
    revenue_growth_yoy: number | null;
    sector_avg_pe: number | null;
    sector_avg_pb: number | null;
    total_assets_idr: number | null;
  };
}

export interface AnalysisResult {
  id: string;
  job_id: string;
  created_at: string;
  candidate_count: number;
  top_candidates: {
    ticker: string;
    companyName: string;
    compositeRank: number;
    layer1Score: string;
    layer2Score: string;
    sentimentScore: string;
  }[];
  prompt: string;
  status: string | null;
}

export interface AnalysisRun {
  job_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}

export const api = {
  async getCandidates(params?: {
    status?: string;
    sector?: string;
    page?: number;
    limit?: number;
  }): Promise<PaginatedResponse<IpoCandidate>> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.sector) searchParams.set("sector", params.sector);
    searchParams.set("page", String(params?.page || 1));
    searchParams.set("limit", String(params?.limit || 20));

    const res = await fetch(`${API_BASE_URL}/candidates/?${searchParams}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch candidates");
    return res.json();
  },

  async getCandidate(id: string): Promise<IpoCandidate> {
    const res = await fetch(`${API_BASE_URL}/candidates/${id}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch candidate");
    return res.json();
  },

  async triggerAnalysis(topN: number = 5, mode?: string): Promise<{ jobId: string }> {
    const res = await fetch(`${API_BASE_URL}/analysis/trigger`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ top_n: topN, mode }),
    });
    if (!res.ok) throw new Error("Failed to trigger analysis");
    return res.json();
  },

  async getAnalysisStatus(jobId: string): Promise<AnalysisRun> {
    const res = await fetch(`${API_BASE_URL}/analysis/${jobId}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch status");
    return res.json();
  },

  async getLatestResults(page = 1, limit = 10): Promise<PaginatedResponse<AnalysisResult>> {
    const res = await fetch(`${API_BASE_URL}/analysis/results/list?page=${page}&limit=${limit}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch results");
    return res.json();
  },

  async getResult(resultId: string): Promise<AnalysisResult> {
    const res = await fetch(`${API_BASE_URL}/analysis/results/${resultId}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch result");
    return res.json();
  },

  async triggerScraper(sources?: string[], tickers?: string[]): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE_URL}/scraper/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sources, tickers }),
    });
    if (!res.ok) throw new Error("Failed to trigger scraper");
    return res.json();
  },

  async getScraperStatus(): Promise<{ waiting: number; active: number; completed: number; failed: number }> {
    const res = await fetch(`${API_BASE_URL}/scraper/status`, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch scraper status");
    return res.json();
  },

  async createCandidate(data: {
    ticker: string;
    company_name: string;
    sector: string;
    listing_date: string;
    offer_price_idr: number;
    underwriter?: string;
    pe_ratio?: number;
    pb_ratio?: number;
    roe?: number;
    debt_to_equity?: number;
    revenue_growth_yoy?: number;
  }): Promise<IpoCandidate> {
    const res = await fetch(`${API_BASE_URL}/candidates/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to create candidate");
    }
    return res.json();
  },

  async triggerPipeline(mode?: string): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE_URL}/scraper/pipeline`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    if (!res.ok) throw new Error("Failed to trigger pipeline");
    return res.json();
  },
};
