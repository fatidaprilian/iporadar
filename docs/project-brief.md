# Project Brief

## Problem Statement

Retail investors on the Indonesia Stock Exchange (BEI) face a selection problem: too many IPO candidates, information scattered across multiple sources, and manual analysis does not scale. A typical BEI IPO cycle can present 5-15 candidates simultaneously. Evaluating each one requires checking the prospectus on e-IPO.co.id, cross-referencing financial statements on idx.co.id, reading news coverage, and comparing against sector benchmarks. Most retail investors skip this process and rely on social media tips or FOMO.

IPO Radar automates the screening and ranking portion of this workflow. It produces one curated recommendation per analysis cycle with transparent reasoning that the user can verify independently (DYOR). The system is a decision support tool -- it narrows the field, it does not make the decision.

## Target Users

Retail investors on BEI who:
- Want a systematic approach to IPO selection
- Can read Indonesian financial news and prospectuses
- Have access to any LLM with web search (Claude, ChatGPT, Gemini) for the final analysis step
- Understand that ML predictions are probabilistic, not deterministic

## Scope

### In Scope

- IPOs on Bursa Efek Indonesia (BEI) only
- Classification: outperform / underperform relative to IHSG (composite index)
- Two prediction horizons: first-day return and 30-day post-IPO return
- Output: ranked candidates + one structured copy-paste prompt for external LLM analysis
- Historical training data: BEI IPOs from 2020-2024 (~300 samples)

### Out of Scope

- Exact price prediction (classification only, not regression)
- Non-IPO stocks or stocks outside BEI
- Horizons beyond 90 days (insufficient evidence in literature)
- Profit guarantees (probabilistic system)
- Automated trade execution
- LLM integration in codebase (prompt is copy-pasted by user)

## Research Foundation

Based on 5 rounds of consensus research across Q1-Q2 journals (2021-2026):

| Finding | Source | Implication |
|---------|--------|-------------|
| Hybrid ensemble + sentiment outperforms single-model baselines | Multiple papers, consistent across rounds | Use ensemble models (XGBoost/Bagging), not standalone classifiers |
| Bagging achieves AUC 0.90 for IPO classification | Alahmadi, 2025 | AUC > 0.85 is a realistic target for Layer 1 |
| XLM-RoBERTa adds +10% accuracy overall, +25% event-driven | Ridhawi, 2026 | Sentiment is a strong short-horizon signal worth engineering |
| Sentiment effect strongest at short horizons, weakens past 30 days | Multiple papers | Weight sentiment higher in Layer 1, reduce in Layer 2 |
| Retail-dominated markets more predictable than efficient markets | Multiple papers | BEI is retail-heavy, which supports the approach |
| No Q1-Q2 paper applies this method to BEI IPOs | Literature gap | Research contribution of this project |

## Data Sources

### Post-IPO Price Data
- **Source:** Yahoo Finance via yfinance Python library
- **Format:** OHLCV daily, `.JK` suffix for BEI tickers
- **Known limitation:** First-day IPO data is sometimes incomplete in yfinance

### Pre-IPO Fundamental Data
- **Source:** e-IPO.co.id (scraping), idx.co.id (financial reports)
- **Format:** Manual scraping, no official API
- **Extracted data:** offer price, share count, underwriter, sector, latest financial statements (revenue, assets, liabilities, equity, net income)

### Sentiment Data
- **Source:** Google News, Indonesian financial news sites
- **Processing:** XLM-RoBERTa multilingual model for sentiment extraction
- **Window:** 7-14 days before listing date
- **Known limitation:** XLM-RoBERTa is multilingual but not fine-tuned specifically on Indonesian financial text. Performance needs empirical validation in Phase 2.

### Data Joining
Pre-IPO (e-IPO + IDX) and post-IPO (yfinance) data are joined on stock ticker code and listing date. This join is manual due to lack of a shared identifier across sources.

## Assumptions to Validate

1. yfinance `.JK` suffix reliably returns BEI IPO data for the 2020-2024 period, including first-day prices.
2. e-IPO.co.id website structure is stable enough for automated scraping.
3. XLM-RoBERTa multilingual model produces useful sentiment scores on Indonesian financial headlines without domain-specific fine-tuning.
4. ~300 IPO samples is sufficient for tree-based classification (likely yes given feature count, but needs cross-validation confirmation).
5. BEI sector classification is stable enough to use as a categorical feature.

## Next Validation Action

Phase 1 data collection will test assumptions 1, 2, and 5. Phase 2 model training will test assumptions 3 and 4.
