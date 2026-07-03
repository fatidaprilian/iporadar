# API Contract

## Overview

Single FastAPI monolith (port 8000) serving REST API consumed by the Next.js dashboard.

All endpoints use JSON request/response bodies. All timestamps are ISO 8601 UTC. Field names use `snake_case`.

Base URL: `http://localhost:8000/api/v1`

---

### Health

#### `GET /health`

```json
{
  "status": "healthy",
  "modelsLoaded": true
}
```

---

### IPO Candidates

#### `GET /candidates/`

List candidates with optional filtering.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | - | Filter: `upcoming`, `listed` |
| `sector` | string | - | Filter by sector name |
| `page` | integer | 1 | Page number |
| `limit` | integer | 20 | Items per page (max 100) |

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "ticker": "XXXX",
      "company_name": "PT Example Tbk",
      "sector": "Technology",
      "listing_date": "2024-03-15",
      "offer_price_idr": 500,
      "share_count": 1000000000,
      "underwriter": "Mandiri Sekuritas",
      "underwriter_tier": 1,
      "status": "listed",
      "fundamental": {
        "pe_ratio": 15.2,
        "pb_ratio": 2.1,
        "roe": 0.18,
        "debt_to_equity": 0.45,
        "total_assets_idr": 5000000000000,
        "revenue_growth_yoy": 0.25,
        "sector_avg_pe": 20.0,
        "sector_avg_pb": 3.0
      }
    }
  ],
  "meta": {
    "page": 1,
    "limit": 20,
    "total": 300,
    "totalPages": 15
  }
}
```

#### `GET /candidates/{id}`

Single candidate with fundamental, news_articles, and predictions.

#### `POST /candidates/`

Create a new candidate. Uniqueness enforced on `ticker`.

#### `PATCH /candidates/{id}`

Partial update.

---

### Analysis

#### `POST /analysis/trigger`

Trigger a new analysis cycle as a background task.

**Request Body:**

```json
{
  "top_n": 5,
  "candidate_ids": ["uuid1", "uuid2"]
}
```

- `candidate_ids`: Optional. If omitted, analyzes upcoming + recently listed candidates.
- `top_n`: Number of top candidates in prompt. Default: 5.

**Response (200):**

```json
{
  "jobId": "uuid",
  "status": "queued",
  "message": "Analysis job queued"
}
```

#### `GET /analysis/{job_id}`

Check analysis job status.

```json
{
  "job_id": "uuid",
  "status": "completed",
  "started_at": "2026-07-03T09:00:00Z",
  "completed_at": "2026-07-03T09:00:03Z",
  "error_message": null
}
```

Status values: `queued`, `processing`, `completed`, `failed`.

#### `GET /analysis/results/list`

Paginated list of analysis results.

| Param | Type | Default |
|-------|------|---------|
| `page` | integer | 1 |
| `limit` | integer | 10 |

```json
{
  "data": [
    {
      "id": "uuid",
      "job_id": "uuid",
      "created_at": "2026-07-03T09:00:03Z",
      "candidate_count": 5,
      "top_candidates": [
        {
          "ticker": "XXXX",
          "companyName": "PT Example Tbk",
          "compositeRank": 1,
          "layer1Score": "0.82",
          "layer2Score": "0.71",
          "sentimentScore": "0.45"
        }
      ],
      "prompt": "Full prompt text...",
      "status": "completed"
    }
  ],
  "meta": { "page": 1, "limit": 10, "total": 5, "totalPages": 1 }
}
```

#### `GET /analysis/results/{result_id}`

Single analysis result with full prompt.

---

### Prediction

#### `POST /predict/`

Run ML predictions for specific candidates.

**Request Body:**

```json
{
  "candidate_ids": ["uuid1"]
}
```

**Response (200):**

```json
{
  "prediction_ids": ["uuid"],
  "message": "Generated predictions for 1 candidates"
}
```

---

### Sentiment

#### `POST /sentiment/`

Extract sentiment from text using XLM-RoBERTa.

**Request Body:**

```json
{
  "texts": ["IPO Example disambut antusias investor"]
}
```

**Response (200):**

```json
{
  "results": [
    {
      "text": "IPO Example disambut antusias investor",
      "sentiment_score": 0.62,
      "magnitude": 0.85,
      "label": "positive"
    }
  ]
}
```

---

### Scraper

#### `POST /scraper/run`

Trigger scraping from configured sources.

```json
{
  "sources": ["eipo", "yfinance", "news"],
  "tickers": ["XXXX"]
}
```

#### `GET /scraper/status`

Current scraper job counts (waiting, active, completed, failed).

---

## Error Format

FastAPI validation errors:

```json
{
  "detail": [
    {
      "loc": ["body", "top_n"],
      "msg": "value is not a valid integer",
      "type": "type_error.integer"
    }
  ]
}
```

HTTP status codes: 200, 400, 404, 422, 500.
