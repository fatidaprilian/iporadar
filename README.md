# IPO Radar

Decision support system for selecting IPO candidates on the Indonesia Stock Exchange (BEI). The system combines ML classification models with multilingual sentiment analysis to rank IPO candidates, then generates a structured prompt that users can paste into any LLM with web search for final comparative analysis.

This is a decision support tool, not an oracle. The final investment decision always belongs to the user.

## What It Does

1. **Scrapes** pre-IPO fundamental data from e-IPO.co.id and IDX, plus post-IPO price data from Yahoo Finance.
2. **Classifies** each IPO candidate as outperform/underperform using two cascading ML layers:
   - Layer 1: First-day return prediction (XGBoost/Bagging, fundamentals + sentiment)
   - Layer 2: 30-day post-IPO prediction (Gradient Boosted Tree, fundamentals + sentiment + technicals)
3. **Scores** candidates using a composite rank (Layer 1: 50%, Layer 2: 30%, Sentiment: 20%).
4. **Generates** a structured copy-paste-ready prompt with all candidate data, ML scores, and a 6-step analysis framework.
5. **Displays** results in a dashboard where users can copy the prompt and paste it into Claude, ChatGPT, Gemini, or any LLM with web search.

## Architecture

| Service | Stack | Purpose |
|---------|-------|---------|
| `api` | FastAPI (Python 3.11) | REST API, ML inference, XLM-RoBERTa sentiment, scraper, orchestration |
| `web` | Node.js 22 (Next.js) | Dashboard frontend |
| `postgres` | PostgreSQL 16 | Data persistence |

All services run via Docker Compose.

## Prerequisites

- Docker and Docker Compose
- Git

## Quick Start

```bash
git clone <repo-url> iporadar
cd iporadar
cp .env.example .env
docker compose up -d
```

Services will be available at:
- Dashboard: http://localhost:3000
- API (FastAPI): http://localhost:8000

## Configuration

Copy `.env.example` to `.env` and set the required values. See `docs/` for detailed configuration options.

## Project Documentation

| Document | Purpose |
|----------|---------|
| [docs/doc-index.md](docs/doc-index.md) | Routing map for all project docs |
| [docs/project-brief.md](docs/project-brief.md) | Problem statement, scope, research foundation |
| [docs/architecture-decision-record.md](docs/architecture-decision-record.md) | Technical decisions and rationale |
| [docs/flow-overview.md](docs/flow-overview.md) | Data pipeline and analysis cycle diagrams |
| [docs/api-contract.md](docs/api-contract.md) | REST API specifications |
| [docs/database-schema.md](docs/database-schema.md) | PostgreSQL schema design |
| [docs/DESIGN.md](docs/DESIGN.md) | Dashboard UI design direction |

## Research Foundation

Based on 5 rounds of consensus research (Q1-Q2 journals, 2021-2026). Key findings:
- Hybrid ensemble + sentiment outperforms single-model baselines consistently
- Bagging achieves AUC 0.90 for IPO classification (Alahmadi, 2025)
- XLM-RoBERTa provides +10% accuracy overall, +25% for event-driven scenarios (Ridhawi, 2026)
- No existing Q1-Q2 paper applies this methodology to BEI IPOs -- this is the research gap

## License

Private. Not for redistribution.
