# UI Design Direction

## Scope

Dashboard for a single-user IPO decision support tool. The primary user workflow is: trigger analysis, review ranked candidates, copy the generated prompt, paste into an external LLM. Secondary workflows: browse historical recommendations, check past prediction accuracy.

No auth screens needed for Phase 1-3. No mobile optimization required initially (desktop-first tool).

## Design Constraints

- Framework: Next.js with Tailwind CSS (explicit user constraint)
- No complex state management (React Query for server state)
- Copy-to-clipboard is the most important interaction (prompt output)
- Data-heavy screens: tables, scores, charts
- Indonesian language for domain-specific labels (ticker names, sector names, news headlines); English for UI chrome

## Pages

### 1. Dashboard (Home)

Primary screen. Shows:
- Current analysis status (idle, running, completed)
- Quick action: "Run Analysis" button
- Latest analysis result summary (if available):
  - Top candidate with composite score
  - Candidate comparison table (rank, ticker, L1 score, L2 score, sentiment)
  - Link to full prompt

### 2. Analysis Result

Detailed view of a single analysis run. Shows:
- Run metadata (timestamp, trigger type, candidate count)
- Ranked candidate cards with:
  - Ticker, company name, sector
  - Layer 1 score (gauge or bar)
  - Layer 2 score (gauge or bar)
  - Sentiment score (color-coded)
  - Key fundamentals (P/E, P/B, ROE, D/E)
  - Red flags if any
- Generated prompt panel:
  - Full prompt text in a monospace container
  - "Copy to Clipboard" button (prominent, primary action)
  - Character count
  - Timestamp of generation

### 3. History

List of past analysis runs. Each row shows:
- Date/time
- Trigger type (manual/scheduled)
- Top recommendation (ticker)
- Composite score
- Actual performance (if enough time has passed for first-day/30-day tracking)

Click to expand into the full Analysis Result view.

### 4. Candidate Browser

Searchable, filterable table of all IPO candidates in the database:
- Columns: ticker, company, sector, listing date, status, offer price
- Filters: status (upcoming/listed), sector, date range
- Click to view candidate detail with fundamentals, price history chart, news articles, and historical predictions

## Component Inventory

| Component | Used In | Notes |
|-----------|---------|-------|
| ScoreGauge | Analysis Result | Circular or semicircular gauge for probability scores |
| SentimentBadge | Analysis Result, Candidate | Color-coded badge: green (positive), red (negative), gray (neutral) |
| CandidateCard | Analysis Result | Summary card with key metrics per candidate |
| CandidateTable | Dashboard, History | Sortable comparison table |
| PromptPanel | Analysis Result | Monospace text display with copy button |
| StatusIndicator | Dashboard | Shows analysis job status with animation for running state |
| RedFlagAlert | Analysis Result | Warning banner when red flags are detected |
| PriceChart | Candidate Detail | Simple OHLCV line chart for post-IPO prices |
| FundamentalTable | Candidate Detail | Key-value table for financial metrics |

## Color Direction

Light theme by default. Dark mode available as a user toggle (persisted in localStorage).

Accent colors (both themes):
- Green for positive signals, outperform labels
- Red for negative signals, underperform labels
- Amber for warnings and red flags
- Blue for neutral actions and links

Light theme: white/light gray backgrounds, dark text, subtle borders.
Dark theme: dark gray/near-black backgrounds, light text, muted borders.

Exact palette to be defined during implementation using Tailwind CSS custom theme config.

## Typography

System font stack with monospace fallback for prompt text and numerical data. No custom web fonts needed for MVP.

## Assumptions to Validate

1. Single-page dashboard is sufficient; multi-page with routing may be needed if the candidate browser grows complex.
2. Copy-to-clipboard works reliably across target browsers (modern Chrome/Firefox/Edge).
3. Prompt text fits in a scrollable container without performance issues (estimated max ~2000 words per prompt).
