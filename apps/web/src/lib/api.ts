export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface IpoCandidate {
  id: string;
  ticker: string;
  company_name: string;
  sector: string;
  listing_date: string;
  offer_price_idr: number;
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

export const api = {
  async getCandidates(): Promise<IpoCandidate[]> {
    const res = await fetch(`${API_BASE_URL}/candidates/?limit=50`, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch candidates");
    const json = await res.json();
    return json.data || [];
  },

  async triggerAnalysis(topN: number = 5): Promise<{ jobId: string }> {
    const res = await fetch(`${API_BASE_URL}/analysis/trigger`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ top_n: topN }),
    });
    if (!res.ok) throw new Error("Failed to trigger analysis");
    return res.json();
  },

  async getAnalysisStatus(jobId: string): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE_URL}/analysis/${jobId}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch status");
    return res.json();
  },

  async getLatestResults(): Promise<AnalysisResult[]> {
    const res = await fetch(`${API_BASE_URL}/analysis/results/list?limit=5`, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch results");
    const json = await res.json();
    return json.data || [];
  },
};
