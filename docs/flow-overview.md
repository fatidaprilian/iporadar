# Flow Overview

## System Architecture

```mermaid
graph TB
    subgraph External["External Data Sources"]
        EIPO["e-IPO.co.id"]
        IDX["idx.co.id"]
        YF["Yahoo Finance"]
        GN["Google News"]
    end

    subgraph Docker["Docker Compose"]
        subgraph API["api (FastAPI Monolith)"]
            Scraper["Python Scraper Module"]
            PriceFetcher["Price Fetcher (yfinance)"]
            NewsScraper["News Scraper (feedparser)"]
            Scheduler["FastAPI BackgroundTasks"]
            PromptBuilder["Prompt Builder"]
            APIRoutes["REST API"]
            FeatEng["Feature Engineering"]
            Sentiment["XLM-RoBERTa Sentiment"]
            Layer1["Layer 1: XGBoost/Bagging"]
            Layer2["Layer 2: GBT"]
            Scoring["Scoring & Ranking"]
        end

        subgraph Web["web (Next.js)"]
            Dashboard["Dashboard UI"]
            PromptDisplay["Prompt Copy Panel"]
            History["Recommendation History"]
        end

        PG["PostgreSQL 16\n(or SQLite)"]
    end

    subgraph User["User Workflow"]
        CopyPrompt["Copy Prompt"]
        ExtLLM["External LLM\n(Claude/ChatGPT/Gemini)"]
        Decision["Investment Decision"]
    end

    EIPO --> Scraper
    IDX --> Scraper
    YF --> PriceFetcher
    GN --> NewsScraper

    Scraper --> PG
    PriceFetcher --> PG
    NewsScraper --> PG

    Scheduler --> APIRoutes

    PG --> FeatEng
    PG --> Sentiment
    FeatEng --> Layer1
    FeatEng --> Layer2
    Sentiment --> Layer1
    Sentiment --> Layer2
    Layer1 --> Scoring
    Layer2 --> Scoring

    Scoring --> APIRoutes
    APIRoutes --> PG
    APIRoutes --> PromptBuilder
    PromptBuilder --> APIRoutes

    Dashboard --> APIRoutes
    APIRoutes --> Dashboard
    PromptBuilder --> PromptDisplay

    PromptDisplay --> CopyPrompt
    CopyPrompt --> ExtLLM
    ExtLLM --> Decision
```

## Analysis Cycle (Happy Path)

```mermaid
sequenceDiagram
    actor User
    participant Web as Next.js Dashboard
    participant API as FastAPI Monolith
    participant BG as BackgroundTasks
    participant PG as PostgreSQL

    User->>Web: Trigger analysis
    Web->>API: POST /api/v1/analysis/trigger
    API->>BG: Spawn background task

    Note over BG,PG: Phase 1: Data Collection (Optional if cached)
    BG->>BG: Execute scraping job (Playwright/RSS)
    BG->>PG: Store IPO fundamental data
    BG->>PG: Store price data (yfinance)
    BG->>PG: Store news articles

    Note over BG,PG: Phase 2: ML Inference
    BG->>PG: Read features (bulk)
    BG->>BG: XLM-RoBERTa sentiment extraction
    BG->>BG: Feature engineering
    BG->>BG: Layer 1 inference (first-day)
    BG->>BG: Layer 2 inference (30-day)
    BG->>BG: Composite scoring & ranking

    Note over BG,PG: Phase 3: Prompt Generation
    BG->>PG: Store predictions
    BG->>BG: Build prompt (top N candidates)

    BG->>PG: Store analysis result + prompt
    BG-->>API: Task complete

    Note over User,Web: Phase 4: User Action
    User->>Web: Check results
    Web->>API: GET /api/v1/analysis/results
    API-->>Web: Return results + prompt
    Web->>User: Display results + prompt
    User->>User: Copy prompt
    User->>User: Paste into external LLM
    User->>User: Read LLM analysis
    User->>User: Make investment decision
```

## Data Pipeline Flow

```mermaid
flowchart LR
    subgraph Collection["Data Collection"]
        A1["e-IPO Scraper\n(fundamentals)"]
        A2["IDX Scraper\n(financials)"]
        A3["yfinance Fetcher\n(OHLCV prices)"]
        A4["News Scraper\n(headlines)"]
    end

    subgraph Cleaning["Data Pipeline"]
        B1["Validate &\nNormalize"]
        B2["Join on ticker\n+ listing date"]
        B3["Handle missing\nvalues"]
    end

    subgraph Features["Feature Engineering"]
        C1["Fundamental\nMetrics"]
        C2["Technical\nIndicators"]
        C3["Sentiment\nScores"]
    end

    subgraph Models["ML Models"]
        D1["Layer 1\nXGBoost/Bagging\n(fundamentals +\nsentiment)"]
        D2["Layer 2\nGBT\n(all features +\nLayer 1 output)"]
    end

    subgraph Output["Output"]
        E1["Composite\nScoring"]
        E2["Candidate\nRanking"]
        E3["Prompt\nGeneration"]
    end

    A1 --> B1
    A2 --> B1
    A3 --> B1
    A4 --> B1
    B1 --> B2
    B2 --> B3

    B3 --> C1
    B3 --> C2
    B3 --> C3

    C1 --> D1
    C3 --> D1
    C1 --> D2
    C2 --> D2
    C3 --> D2
    D1 --> D2

    D1 --> E1
    D2 --> E1
    C3 --> E1
    E1 --> E2
    E2 --> E3
```

## Scoring Logic

The composite score for each IPO candidate uses a weighted average:

| Component | Weight | Source |
|-----------|--------|--------|
| Layer 1 score (first-day probability) | 50% | XGBoost/Bagging output |
| Layer 2 score (30-day probability) | 30% | GBT output |
| Sentiment score (normalized 0-1) | 20% | XLM-RoBERTa |

Candidates are ranked by composite score descending. Top N (default: 3-5) are included in the generated prompt. Candidates with Layer 1 score below 50% are excluded regardless of other scores.

## Scheduled vs Manual Triggers

| Trigger | Mechanism | When |
|---------|-----------|------|
| Manual | User clicks "Run Analysis" in dashboard | On demand |
| Scheduled | FastAPI APScheduler/Cron (Phase 4) | Configurable (default: daily at market open, 09:00 WIB) |

Both triggers execute the same analysis cycle sequence. Scheduled runs store results and the user reviews them later.
