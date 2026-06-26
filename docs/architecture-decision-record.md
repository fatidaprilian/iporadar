# Architecture Decision Record

## ADR-001: Two-Process Topology (Modular Monolith + Separate ML Service)

**Status:** Accepted  
**Date:** 2026-06-24

### Context

The system requires two fundamentally different runtimes: Node.js for the API/orchestration layer and Python for ML inference and NLP. A single-process monolith is not feasible because the ML stack (scikit-learn, XGBoost, transformers) is Python-native with no viable Node.js equivalent. A full microservices split is not justified at ~300 samples and a single-user workload.

### Decision

Two processes, each in its own Docker container, communicating via REST over the Docker network:

| Process | Runtime | Owns |
|---------|---------|------|
| API server (NestJS) | Node.js 22 | PostgreSQL schema, scraper orchestration, scheduling, prompt builder |
| ML service (FastAPI) | Python 3.11 | Model inference, sentiment analysis, feature engineering |

PostgreSQL and Redis run as additional containers. The NestJS API is the primary database owner. The ML service reads training data from PostgreSQL directly (read-only) and writes predictions back through the NestJS API.

### Rationale

- Per SVC-001: "Default to modular monoliths unless scale explicitly dictates microservices." This is a monolith with a language boundary, not a microservices architecture.
- FastAPI over subprocess: the blueprint considered subprocess bridging. Subprocess is fragile for long-running ML inference -- no health checks, no independent restart, timeout management is manual. FastAPI adds minimal overhead and provides OpenAPI docs automatically.
- Shared database is acceptable because the ML service does not own or mutate the schema. It reads features for training and returns predictions through the API.

### Alternatives Considered

1. **Subprocess bridging:** NestJS spawns Python processes for each inference call. Rejected: fragile, no health checks, process lifecycle management is complex.
2. **Full microservices:** Separate databases per service, message queue for communication. Rejected: over-engineering for ~300 samples and single-user scale.
3. **Python monolith (FastAPI only):** Drop NestJS entirely. Rejected: blueprint explicitly specifies NestJS + Bull Queue, and Node.js is a stronger fit for the scheduler/orchestration layer.

---

## ADR-002: No LLM in Codebase (Prompt Builder Pattern)

**Status:** Accepted  
**Date:** 2026-06-24

### Context

The blueprint originally described an integrated LLM with web search for comparative analysis. This was revised: no LLM API is integrated into the codebase.

### Decision

The system generates a structured copy-paste-ready prompt containing all candidate data, ML scores, score interpretation guide, and a 6-step analysis framework. The user copies this prompt and pastes it into any external LLM with web search (Claude, ChatGPT, Gemini).

### Rationale

- No dependency on any LLM provider API or self-hosted model.
- No API keys or token costs to manage.
- User controls which LLM they use and can switch freely.
- The prompt includes explicit score interpretation guidance so the LLM does not misread ML outputs.
- The prompt includes a "no recommendation" condition -- if all candidates have material red flags, the LLM should say so instead of forcing a pick.

---

## ADR-003: XLM-RoBERTa for Multilingual Sentiment

**Status:** Accepted  
**Date:** 2026-06-24

### Context

Indonesian financial news is primarily in Bahasa Indonesia. FinBERT is trained on English financial text and has unvalidated performance on Indonesian content.

### Decision

Use XLM-RoBERTa multilingual model for sentiment extraction instead of FinBERT. Specifically, a pre-trained XLM-RoBERTa model fine-tuned on multilingual financial sentiment (to be selected during Phase 2 implementation).

### Rationale

- XLM-RoBERTa handles 100+ languages including Indonesian without translation.
- Avoids the translation pipeline (Indonesian to English) which introduces noise and latency.
- Ridhawi (2026) shows +10% accuracy overall for multilingual transformer sentiment in IPO prediction.
- If no suitable financial-domain fine-tuned model exists, the general XLM-RoBERTa sentiment model is the fallback, with domain fine-tuning as a Phase 2 stretch goal.

### Model Selection (Deferred to Phase 2)

XLM-RoBERTa is the architecture name, not a specific model checkpoint. Likely candidates:
- `cardiffnlp/twitter-xlm-roberta-base-sentiment` (general multilingual sentiment)
- A financial-domain fine-tuned variant if available on HuggingFace

The specific checkpoint selection is a Phase 2 decision based on empirical evaluation against Indonesian financial headlines.

### Assumptions to Validate

- A pre-trained XLM-RoBERTa-based model exists on HuggingFace that handles Indonesian financial sentiment adequately.
- If not, general-purpose XLM-RoBERTa sentiment still adds predictive value over fundamentals-only baseline.

---

## ADR-004: Docker + Docker Compose for Development and Deployment

**Status:** Accepted  
**Date:** 2026-06-24

### Context

The project has 5 services (API, ML service, web, PostgreSQL, Redis) with two different runtimes (Node.js, Python). Managing these manually is error-prone.

### Decision

Use Docker + Docker Compose for all environments. Development uses `docker-compose.yml`. Production will use `docker-compose.prod.yml` with production overrides (Phase 4+).

### Constraints (from DOCK-001)

- Use minimal trusted base images (node:20-slim, python:3.11-slim).
- Do not run as root in production containers.
- Do not bake secrets into image layers.
- Production compose must define explicit healthchecks.
- Verify latest official Docker documentation before writing configuration.

---

## ADR-005: PostgreSQL Schema Ownership

**Status:** Accepted  
**Date:** 2026-06-24

### Context

Both NestJS and Python need access to IPO data. Need to decide schema ownership and migration strategy.

### Decision

NestJS API owns the PostgreSQL schema and all migrations. The ML service connects to PostgreSQL directly for bulk reads (training data, feature extraction) but writes predictions back through the NestJS API endpoints.

### Rationale (from DATA-001)

- Single schema owner prevents migration conflicts.
- ML service read access is pragmatic: loading 300+ rows through REST pagination would add unnecessary complexity. Direct SQL reads for batch operations are simpler.
- Write-through-API ensures data validation and audit logging happen in one place.
- Monetary amounts stored as integer (minor units, IDR).
- All timestamps stored in UTC.

---

## ADR-006: Bull Queue for Scheduled Analysis

**Status:** Accepted  
**Date:** 2026-06-24

### Context

Analysis cycles can be triggered manually or on a schedule. Scraping and ML inference are long-running operations (potentially minutes).

### Decision

Use Bull Queue (backed by Redis) in NestJS for:
- Scheduled analysis cycle triggers (cron-like)
- Background processing of scraping jobs
- Orchestrating ML service calls

### Constraints (from JOB-001)

- All jobs must be idempotent.
- Jobs must have timeouts and retry limits.
- Failed jobs go to a dead-letter queue.
- Jobs exceeding 500ms must run in background queues (all scraping and ML inference qualify).

---

## ADR-007: Tree Models Only for Classification

**Status:** Accepted  
**Date:** 2026-06-24

### Context

~300 IPO samples is too small for deep learning. The research literature confirms tree-based models perform well on tabular IPO data.

### Decision

Use only tree-based models:
- Layer 1: XGBoost and Bagging ensemble (with Random Forest and AdaBoost as comparators)
- Layer 2: Gradient Boosted Tree (with Logistic Regression as comparator)
- No neural networks for classification. XLM-RoBERTa is used only for feature extraction (sentiment scores), not as an end-to-end classifier.

### Rationale

- Alahmadi (2025) achieves AUC 0.90 with Bagging on IPO classification.
- Tree models handle tabular data with mixed types (numeric + categorical) naturally.
- ~300 samples is adequate for tree models with proper cross-validation but insufficient for deep learning.
- Interpretability: feature importance from XGBoost directly informs the prompt builder.
