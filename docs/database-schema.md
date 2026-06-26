# Database Schema

## Overview

Single PostgreSQL 16 database owned by the NestJS API. The ML service has read-only access for bulk feature extraction. All migrations are managed by NestJS (TypeORM).

Constraints per DATA-001:
- All timestamps in UTC (timestamptz).
- Monetary amounts in integer minor units (IDR, no float).
- Multi-table mutations inside transactions.
- Paginate growable datasets.
- Optimistic concurrency via version column where needed.

## Entity Relationship Diagram

```mermaid
erDiagram
    IPO_CANDIDATE ||--o{ PRICE_DATA : has
    IPO_CANDIDATE ||--o{ NEWS_ARTICLE : has
    IPO_CANDIDATE ||--o{ PREDICTION : has
    IPO_CANDIDATE ||--|| FUNDAMENTAL : has
    ANALYSIS_RUN ||--o{ ANALYSIS_CANDIDATE : contains
    ANALYSIS_CANDIDATE }o--|| IPO_CANDIDATE : references
    ANALYSIS_CANDIDATE }o--|| PREDICTION : references
    ANALYSIS_RUN ||--|| ANALYSIS_RESULT : produces

    IPO_CANDIDATE {
        uuid id PK
        varchar ticker UK
        varchar company_name
        varchar sector
        date listing_date
        integer offer_price_idr "minor units"
        bigint share_count
        varchar underwriter
        smallint underwriter_tier "1-3"
        varchar status "upcoming|listed|delisted"
        smallint version "optimistic concurrency"
        timestamptz created_at
        timestamptz updated_at
    }

    FUNDAMENTAL {
        uuid id PK
        uuid candidate_id FK
        numeric pe_ratio "decimal(10,2)"
        numeric pb_ratio "decimal(10,2)"
        numeric roe "decimal(8,4)"
        numeric debt_to_equity "decimal(10,4)"
        bigint total_assets_idr "minor units"
        bigint revenue_idr "minor units"
        bigint net_income_idr "minor units"
        numeric revenue_growth_yoy "decimal(8,4)"
        numeric sector_avg_pe "decimal(10,2)"
        numeric sector_avg_pb "decimal(10,2)"
        timestamptz report_date "financial report date"
        timestamptz created_at
    }

    PRICE_DATA {
        uuid id PK
        uuid candidate_id FK
        date trade_date
        integer open_idr "minor units"
        integer high_idr "minor units"
        integer low_idr "minor units"
        integer close_idr "minor units"
        bigint volume
        timestamptz created_at
    }

    NEWS_ARTICLE {
        uuid id PK
        uuid candidate_id FK
        varchar title
        varchar source "google_news|cnbc_id|etc"
        varchar url
        date published_date
        numeric sentiment_score "decimal(5,3) -1.0 to 1.0"
        numeric sentiment_magnitude "decimal(5,3) 0.0 to 1.0"
        varchar sentiment_label "positive|negative|neutral"
        timestamptz scraped_at
        timestamptz created_at
    }

    PREDICTION {
        uuid id PK
        uuid candidate_id FK
        varchar model_version
        numeric layer1_probability "decimal(6,4)"
        varchar layer1_label "outperform|underperform"
        jsonb layer1_feature_importance
        numeric layer2_probability "decimal(6,4)"
        varchar layer2_label "outperform|underperform"
        jsonb layer2_feature_importance
        numeric sentiment_score "decimal(5,3)"
        numeric sentiment_magnitude "decimal(5,3)"
        integer news_count
        numeric composite_score "decimal(6,4)"
        timestamptz created_at
    }

    ANALYSIS_RUN {
        uuid id PK
        varchar status "queued|processing|completed|failed"
        integer top_n "candidates to include in prompt"
        varchar trigger_type "manual|scheduled"
        timestamptz started_at
        timestamptz completed_at
        varchar error_message "nullable, for failed runs"
        timestamptz created_at
    }

    ANALYSIS_CANDIDATE {
        uuid id PK
        uuid run_id FK
        uuid candidate_id FK
        uuid prediction_id FK
        smallint composite_rank
    }

    ANALYSIS_RESULT {
        uuid id PK
        uuid run_id FK
        integer candidate_count
        text prompt "generated prompt text"
        jsonb top_candidates_summary "denormalized for quick display"
        timestamptz created_at
    }
```

## Tables Detail

### ipo_candidate

Primary entity. One row per IPO. Ticker is unique. Status tracks lifecycle: `upcoming` (announced but not listed), `listed` (trading), `delisted` (removed).

**Indexes:**
- `idx_candidate_ticker` UNIQUE on `ticker`
- `idx_candidate_status` on `status`
- `idx_candidate_listing_date` on `listing_date`
- `idx_candidate_sector` on `sector`

### fundamental

One-to-one with ipo_candidate. Contains financial metrics from the prospectus. All monetary values in IDR minor units (no decimals needed since IDR has no subunits, but stored as bigint for consistency).

**Indexes:**
- `idx_fundamental_candidate` UNIQUE on `candidate_id`

### price_data

Daily OHLCV from yfinance. One row per candidate per trading day. Only populated after listing date.

**Indexes:**
- `idx_price_candidate_date` UNIQUE on `(candidate_id, trade_date)`
- `idx_price_trade_date` on `trade_date`

### news_article

Headlines scraped from Google News and financial sites. Sentiment scores are populated by the ML service after XLM-RoBERTa processing. Each article is processed once; re-scraping the same URL is idempotent.

**Indexes:**
- `idx_news_candidate` on `candidate_id`
- `idx_news_url` UNIQUE on `url`
- `idx_news_published` on `published_date`

### prediction

ML model outputs. One prediction per candidate per model version. Contains both layer scores, feature importance (JSONB for flexibility), and the aggregated sentiment.

**Indexes:**
- `idx_prediction_candidate` on `candidate_id`
- `idx_prediction_candidate_version` UNIQUE on `(candidate_id, model_version)`

### analysis_run

Tracks each analysis cycle (manual or scheduled). Status progresses through `queued` -> `processing` -> `completed` (or `failed`).

**Indexes:**
- `idx_run_status` on `status`
- `idx_run_created` on `created_at`

### analysis_candidate

Join table linking an analysis run to the candidates it evaluated. Stores the composite rank for that run.

**Indexes:**
- `idx_ac_run` on `run_id`
- `idx_ac_candidate` on `candidate_id`

### analysis_result

Stores the generated prompt and a denormalized summary of top candidates for quick dashboard display without joining.

**Indexes:**
- `idx_result_run` UNIQUE on `run_id`

## Migration Strategy

Migrations are TypeORM migration files in `apps/api/src/migrations/`. Each migration is:
- Timestamped (auto-generated by TypeORM CLI)
- Idempotent where possible (use `IF NOT EXISTS`)
- Run via `npm run migration:run` in the API container
- Rollback via `npm run migration:revert`

The initial migration creates all tables. Subsequent migrations add columns, indexes, or new tables as the schema evolves.
