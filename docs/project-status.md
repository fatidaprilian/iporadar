# IPO Radar — Project Status & Blueprint

**Last updated:** 2026-07-03

## Current Position

| Phase | Status | Keterangan |
|-------|--------|------------|
| **Phase 1: Data Foundation & Infrastructure** | Done | PostgreSQL schema, SQLAlchemy ORM, FastAPI boilerplate, Next.js dashboard |
| **Phase 2: Scraping & ML Pipeline** | Done | Playwright e-IPO scraper, RSS news scraper, yfinance, XLM-RoBERTa sentiment, XGBoost wrappers, ML endpoints |
| **Phase 2.5: Monolith Migration** | Done | Menghapus NestJS & Redis, memindahkan semua logika ke FastAPI |
| **Phase 3: Data Collection & ML Training** | Done | Synthetic dataset, XGBoost trained, scraper persists to DB with sentiment |
| **Phase 4: Polish, Testing, Deployment** | In Progress | Frontend pages done, deployment belum |

**Yang sudah jalan:** Semua backend sudah lengkap — scraper (e-IPO, yfinance, news) persist ke DB dengan sentiment analysis, ML pipeline (XGBoost L1/L2 + XLM-RoBERTa), prompt generation. Frontend 4 halaman (Dashboard, Candidates, History, Result Detail) dengan navigasi, filter, pagination.

**Yang belum:** Docker production config, VPS deployment, real data training (saat ini pakai synthetic).

---

## Problem Statement

Investor ritel di BEI kesulitan memilih IPO yang layak dibeli. Terlalu banyak kandidat (5-15 per siklus), informasi tersebar di banyak sumber, dan analisa manual tidak scalable.

**IPO Radar** mengotomasi proses screening dan ranking. Output akhir: **satu rekomendasi terkurasi + prompt terstruktur** yang di-copy-paste ke LLM eksternal (Claude/ChatGPT/Gemini) untuk analisis mendalam.

## Scope

| Dalam Scope | Luar Scope |
|-------------|------------|
| IPO di Bursa Efek Indonesia (BEI) | Saham non-IPO, bursa luar negeri |
| Klasifikasi: outperform/underperform vs IHSG | Prediksi harga eksak |
| Horizon: first-day return & 30-hari post-IPO | Horizon >90 hari |
| 1 rekomendasi final + reasoning perbandingan | Jaminan profit |
| Copy-paste prompt ke LLM eksternal | Integrasi API LLM di codebase |

## Tech Stack

| Layer | Teknologi | Peran |
|-------|-----------|-------|
| API / ML Service | FastAPI (Python 3.11) | Schema owner, REST API, scraper orchestration, BackgroundTasks, Prompt Builder, XGBoost inference, XLM-RoBERTa |
| Frontend | Next.js 15 + TailwindCSS v4 | Dashboard UI, light/dark mode, prompt copy panel |
| Database | PostgreSQL 16 | Semua data (candidates, fundamentals, news, predictions, analysis runs) |
| Containerization | Docker + Docker Compose | Dev & production environments |

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                  Docker Compose                        │
│                                                        │
│  ┌─────────────┐       ┌───────────────────────┐       │
│  │  Next.js    │──────▶│   FastAPI Monolith    │       │
│  │  Dashboard  │       │   (API + ML)          │       │
│  │  :3000      │       │   :8000               │       │
│  └─────────────┘       └───────────┬───────────┘       │
│                                    │                   │
│                                    ▼                   │
│                        ┌───────────────────────┐       │
│                        │     PostgreSQL        │       │
│                        │     :5432             │       │
│                        └───────────────────────┘       │
└────────────────────────────────────────────────────────┘
```

**Keputusan arsitektur kunci:**
- **ADR-008:** Konsolidasi ke FastAPI Monolith (menghapus NestJS dan Redis).
- **ADR-002:** No LLM in codebase — Prompt Builder pattern (copy-paste).
- **ADR-003:** XLM-RoBERTa, bukan FinBERT (bahasa Indonesia).
- **ADR-007:** Tree models only (XGBoost/Bagging), bukan deep learning (~300 sampel).

## ML Pipeline

```
Layer 1 (XGBoost/Bagging)          Layer 2 (GBT)
├── Fundamentals (P/E, P/B, ROE)   ├── Semua fitur Layer 1
├── Sentiment Score (XLM-RoBERTa)   ├── Output Layer 1
└── → First-day return prediction   ├── Technical indicators
                                    └── → 30-day return prediction
```

**Composite Score:** Layer 1 (50%) + Layer 2 (30%) + Sentiment (20%)

## Database Schema

7 tabel utama: `ipo_candidate`, `fundamental`, `price_data`, `news_article`, `prediction`, `analysis_run`, `analysis_result`, `analysis_candidate`.

## Frontend

| Page | Status |
|------|--------|
| Dashboard (Home) | Done |
| Analysis Result Detail | Done |
| History | Done |
| Candidate Browser | Done |

## Deployment Spec

| Resource | Minimum | Catatan |
|----------|---------|---------|
| RAM | 2GB | XLM-RoBERTa ~1GB saat loading |
| Storage | 10GB | Model weights + DB + Docker images |
| CPU | 2 vCPU | XGBoost ringan, Playwright berat |

**Strategi:** Train model di laptop → export `.pkl` → upload ke VPS yang cuma jalankan inference.

## Next Steps

### Phase 4 (Current)
1. Docker production config (multi-stage, non-root, health checks)
2. VPS deployment
3. Real data training with actual IPO historis BEI
