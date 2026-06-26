# API Contract

## Overview

Two REST APIs exist in this system:

1. **NestJS API** (port 3001): Public-facing API consumed by the Next.js dashboard.
2. **ML Service API** (port 8000): Internal API consumed only by the NestJS API. Not exposed outside Docker network in production.

All endpoints use JSON request/response bodies. All timestamps are ISO 8601 UTC.

---

## NestJS API (Public)

Base URL: `http://localhost:3001/api/v1`

### IPO Candidates

#### `GET /ipo-candidates`

List IPO candidates with optional filtering.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | `all` | Filter: `upcoming`, `listed`, `all` |
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
      "companyName": "PT Example Tbk",
      "sector": "Technology",
      "listingDate": "2024-03-15T00:00:00Z",
      "offerPrice": 500,
      "shareCount": 1000000000,
      "underwriter": "Mandiri Sekuritas",
      "underwriterTier": 1,
      "status": "listed",
      "fundamentals": {
        "peRatio": 15.2,
        "pbRatio": 2.1,
        "roe": 0.18,
        "debtToEquity": 0.45,
        "totalAssets": 5000000000000,
        "revenueGrowthYoy": 0.25
      },
      "createdAt": "2024-03-01T00:00:00Z",
      "updatedAt": "2024-03-15T00:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "limit": 20,
    "total": 45,
    "totalPages": 3
  }
}
```

#### `GET /ipo-candidates/:id`

Get a single IPO candidate by ID.

**Response (200):** Single candidate object (same shape as list item).

**Response (404):**

```json
{
  "statusCode": 404,
  "message": "IPO candidate not found",
  "error": "Not Found"
}
```

---

### Analysis

#### `POST /analysis/trigger`

Trigger a new analysis cycle. Enqueues a background job.

**Request Body:**

```json
{
  "candidateIds": ["uuid1", "uuid2"],
  "topN": 5
}
```

- `candidateIds`: Optional. If omitted, analyzes all upcoming/recently listed candidates.
- `topN`: Number of top candidates to include in prompt. Default: 5. Max: 10.

**Response (202):**

```json
{
  "jobId": "uuid",
  "status": "queued",
  "message": "Analysis job queued"
}
```

#### `GET /analysis/:jobId`

Check analysis job status.

**Response (200):**

```json
{
  "jobId": "uuid",
  "status": "completed",
  "startedAt": "2024-03-15T09:00:00Z",
  "completedAt": "2024-03-15T09:03:45Z",
  "resultId": "uuid"
}
```

Status values: `queued`, `processing`, `completed`, `failed`.

#### `GET /analysis/results`

List analysis results (paginated).

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `limit` | integer | 10 | Items per page |

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "jobId": "uuid",
      "createdAt": "2024-03-15T09:03:45Z",
      "candidateCount": 8,
      "topCandidates": [
        {
          "ticker": "XXXX",
          "companyName": "PT Example Tbk",
          "compositeRank": 1,
          "layer1Score": 0.82,
          "layer2Score": 0.71,
          "sentimentScore": 0.45
        }
      ],
      "prompt": "Full prompt text here..."
    }
  ],
  "meta": { "page": 1, "limit": 10, "total": 5, "totalPages": 1 }
}
```

#### `GET /analysis/results/:id`

Get a single analysis result with full prompt text.

---

### Scraper Control

#### `POST /scraper/run`

Trigger a manual scraping run.

**Request Body:**

```json
{
  "sources": ["eipo", "idx", "yfinance", "news"],
  "tickers": ["XXXX", "YYYY"]
}
```

- `sources`: Which scrapers to run. Default: all.
- `tickers`: Optional. If omitted, scrapes all known candidates.

**Response (202):**

```json
{
  "jobId": "uuid",
  "status": "queued"
}
```

#### `GET /scraper/status`

Get current scraper job statuses.

---

## ML Service API (Internal)

Base URL: `http://ml-service:8000/api/v1`

This API is internal to the Docker network. Not exposed to the frontend.

### Health

#### `GET /health`

**Response (200):**

```json
{
  "status": "healthy",
  "modelsLoaded": true,
  "sentimentModelLoaded": true
}
```

### Prediction

#### `POST /predict`

Run ML inference on a batch of IPO candidates.

**Request Body:**

```json
{
  "candidates": [
    {
      "ticker": "XXXX",
      "fundamentals": {
        "offerPrice": 500,
        "sectorAvgPrice": 1200,
        "underwriterTier": 1,
        "totalAssets": 5000000000000,
        "marketCap": 2000000000000,
        "sector": "Technology",
        "peRatio": 15.2,
        "pbRatio": 2.1,
        "roe": 0.18,
        "debtToEquity": 0.45
      },
      "sentimentData": {
        "headlines": ["Headline 1", "Headline 2"],
        "newsCount": 12
      },
      "technicalData": {
        "prices": [500, 520, 510, 530],
        "volumes": [1000000, 800000, 900000, 1100000]
      }
    }
  ]
}
```

- `technicalData` is optional. If absent, Layer 2 uses fundamentals + sentiment + Layer 1 output only.

**Response (200):**

```json
{
  "predictions": [
    {
      "ticker": "XXXX",
      "layer1": {
        "label": "outperform",
        "probability": 0.82,
        "featureImportance": {
          "roe": 0.15,
          "sentimentScore": 0.12,
          "underwriterTier": 0.11
        }
      },
      "layer2": {
        "label": "outperform",
        "probability": 0.71,
        "featureImportance": {
          "rsi": 0.18,
          "peRatio": 0.14,
          "layer1Score": 0.12
        }
      },
      "sentiment": {
        "score": 0.45,
        "magnitude": 0.78,
        "articleCount": 12
      },
      "compositeScore": 0.72,
      "compositeRank": 1
    }
  ],
  "modelVersions": {
    "layer1": "v1.0.0",
    "layer2": "v1.0.0",
    "sentiment": "xlm-roberta-base"
  }
}
```

### Sentiment

#### `POST /sentiment`

Extract sentiment from headlines without running full prediction.

**Request Body:**

```json
{
  "headlines": [
    { "text": "PT Example Tbk siap melantai di BEI", "source": "google_news" },
    { "text": "IPO Example disambut antusias investor", "source": "cnbc_indonesia" }
  ]
}
```

**Response (200):**

```json
{
  "results": [
    { "text": "...", "score": 0.45, "magnitude": 0.78, "label": "positive" },
    { "text": "...", "score": 0.62, "magnitude": 0.85, "label": "positive" }
  ],
  "aggregated": {
    "meanScore": 0.535,
    "meanMagnitude": 0.815,
    "positiveCount": 2,
    "negativeCount": 0,
    "neutralCount": 0
  }
}
```

---

## Error Response Format

All endpoints use a consistent error format:

```json
{
  "statusCode": 400,
  "message": "Validation error: ticker is required",
  "error": "Bad Request"
}
```

HTTP status codes used: 200, 202, 400, 404, 422, 500, 503.

## Idempotency

Per API-001: all mutation endpoints (POST) accept an optional `Idempotency-Key` header. If provided, duplicate requests with the same key return the original response without re-executing the operation.
