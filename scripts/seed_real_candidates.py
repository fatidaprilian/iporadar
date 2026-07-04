"""Seed the database with real IPO candidates from the training dataset.

Uses real fundamentals from data/real_fundamentals.json for deterministic scores.

Usage:
    python3 scripts/seed_real_candidates.py
"""

import csv
import json
import math
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "api"))

INPUT_CSV = ROOT / "data" / "ipo_training_dataset.csv"
FUNDAMENTALS_JSON = ROOT / "data" / "real_fundamentals.json"

SECTOR_PROFILES = {
    "Basic Materials": {"pe": 12.0, "pb": 2.0, "roe": 0.15, "de": 0.8, "rev_growth": 0.10, "avg_pe": 12.0, "avg_pb": 2.0},
    "Technology": {"pe": 28.0, "pb": 4.5, "roe": 0.12, "de": 0.3, "rev_growth": 0.30, "avg_pe": 28.0, "avg_pb": 4.5},
    "Financial Services": {"pe": 10.0, "pb": 1.5, "roe": 0.14, "de": 5.0, "rev_growth": 0.12, "avg_pe": 10.0, "avg_pb": 1.5},
    "Consumer Cyclical": {"pe": 22.0, "pb": 3.2, "roe": 0.16, "de": 0.5, "rev_growth": 0.18, "avg_pe": 22.0, "avg_pb": 3.2},
    "Consumer Staples": {"pe": 18.0, "pb": 2.8, "roe": 0.18, "de": 0.4, "rev_growth": 0.12, "avg_pe": 18.0, "avg_pb": 2.8},
    "Property": {"pe": 15.0, "pb": 1.8, "roe": 0.10, "de": 1.2, "rev_growth": 0.08, "avg_pe": 15.0, "avg_pb": 1.8},
    "Industrials": {"pe": 14.0, "pb": 2.2, "roe": 0.12, "de": 1.0, "rev_growth": 0.10, "avg_pe": 14.0, "avg_pb": 2.2},
    "Energy": {"pe": 10.0, "pb": 1.5, "roe": 0.16, "de": 0.7, "rev_growth": 0.12, "avg_pe": 10.0, "avg_pb": 1.5},
    "Utilities": {"pe": 16.0, "pb": 2.0, "roe": 0.11, "de": 1.5, "rev_growth": 0.06, "avg_pe": 16.0, "avg_pb": 2.0},
    "Healthcare": {"pe": 25.0, "pb": 3.5, "roe": 0.15, "de": 0.4, "rev_growth": 0.20, "avg_pe": 25.0, "avg_pb": 3.5},
    "Telecommunications": {"pe": 18.0, "pb": 2.5, "roe": 0.13, "de": 0.6, "rev_growth": 0.08, "avg_pe": 18.0, "avg_pb": 2.5},
    "Mining": {"pe": 10.0, "pb": 1.8, "roe": 0.14, "de": 0.9, "rev_growth": 0.08, "avg_pe": 10.0, "avg_pb": 1.8},
}

DEFAULT_PROFILE = {"pe": 15.0, "pb": 2.5, "roe": 0.12, "de": 0.8, "rev_growth": 0.10, "avg_pe": 15.0, "avg_pb": 2.5}


def sanitize_value(val, low, high, default):
    if val is None:
        return default
    return max(low, min(high, val))


def main():
    import os
    os.environ.setdefault("DATABASE_URL", "postgresql://iporadar:iporadar_dev@localhost:5432/iporadar")

    from app.database import SessionLocal, engine, Base
    from app.models import IpoCandidate, Fundamental, CandidateStatus, PriceData, NewsArticle, Prediction, AnalysisCandidate, AnalysisResult, AnalysisRun

    if not INPUT_CSV.exists():
        print(f"Training dataset not found: {INPUT_CSV}")
        sys.exit(1)

    if not FUNDAMENTALS_JSON.exists():
        print(f"Real fundamentals not found: {FUNDAMENTALS_JSON}")
        sys.exit(1)

    with open(FUNDAMENTALS_JSON) as f:
        real_fundamentals = json.load(f)
    print(f"Loaded real fundamentals for {len(real_fundamentals)} tickers")

    db = SessionLocal()

    print("Clearing old data...")
    db.query(AnalysisCandidate).delete()
    db.query(AnalysisResult).delete()
    db.query(AnalysisRun).delete()
    db.query(Prediction).delete()
    db.query(NewsArticle).delete()
    db.query(PriceData).delete()
    db.query(Fundamental).delete()
    db.query(IpoCandidate).delete()
    db.commit()
    print("  Cleared all tables.")

    with open(INPUT_CSV, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\nSeeding {len(rows)} real IPO candidates...")

    for row in rows:
        ticker = row["ticker"]
        sector = row["sector"]
        profile = SECTOR_PROFILES.get(sector, DEFAULT_PROFILE)
        offer_price = int(row["offer_price_idr"])

        listing_date = datetime.strptime(row["listing_date"], "%Y-%m-%d").date()
        status = CandidateStatus.LISTED
        tier = int(row["underwriter_tier"])

        candidate = IpoCandidate(
            id=str(uuid.uuid4()),
            ticker=ticker,
            company_name=row["company_name"],
            sector=sector,
            listing_date=listing_date,
            offer_price_idr=offer_price,
            underwriter=row["underwriter"],
            underwriter_tier=tier,
            status=status,
        )
        db.add(candidate)
        db.flush()

        fin = real_fundamentals.get(ticker, {})

        pe_raw = fin.get("pe_ratio")
        if pe_raw is not None and pe_raw < 0:
            pe = 200.0
        else:
            pe = sanitize_value(pe_raw, 0.1, 500.0, profile["pe"])

        pb = sanitize_value(fin.get("pb_ratio"), 0.01, 100.0, profile["pb"])
        if fin.get("pb_ratio") is not None and fin["pb_ratio"] < 0:
            pb = 0.01

        roe = sanitize_value(fin.get("roe"), -2.0, 1.0, 0.0)
        de = sanitize_value(fin.get("debt_to_equity"), 0.0, 10.0, profile["de"])
        rev_growth = sanitize_value(fin.get("revenue_growth_yoy"), -1.0, 5.0, 0.0)

        total_assets = fin.get("total_assets")
        if total_assets is None:
            total_assets = fin.get("market_cap")

        fundamental = Fundamental(
            id=str(uuid.uuid4()),
            candidate_id=candidate.id,
            pe_ratio=round(pe, 2),
            pb_ratio=round(pb, 2),
            roe=round(roe, 4),
            debt_to_equity=round(de, 4),
            revenue_growth_yoy=round(rev_growth, 4),
            sector_avg_pe=profile["avg_pe"],
            sector_avg_pb=profile["avg_pb"],
            total_assets_idr=int(total_assets) if total_assets else None,
        )
        db.add(fundamental)

        print(f"  {ticker}: PE={round(pe, 1)}, PB={round(pb, 2)}, ROE={round(roe, 3)}, "
              f"D/E={round(de, 2)}, RevG={round(rev_growth, 3)}")

    db.commit()
    db.close()

    print(f"\nDone! {len(rows)} real candidates seeded with real fundamentals.")
    print("Scores will now be deterministic (same fundamentals every run).")


if __name__ == "__main__":
    main()
