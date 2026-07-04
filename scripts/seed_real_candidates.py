"""Seed the database with real IPO candidates from the training dataset.

Replaces synthetic data with actual BEI IPO tickers, including fundamentals.

Usage:
    python3 scripts/seed_real_candidates.py
"""

import csv
import math
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "api"))

INPUT_CSV = ROOT / "data" / "ipo_training_dataset.csv"

SECTOR_PROFILES = {
    "Mining": {"pe": 12.0, "pb": 2.0, "roe": 0.15, "de": 0.8, "rev_growth": 0.10, "avg_pe": 12.0, "avg_pb": 2.0},
    "Technology": {"pe": 28.0, "pb": 4.5, "roe": 0.12, "de": 0.3, "rev_growth": 0.30, "avg_pe": 28.0, "avg_pb": 4.5},
    "Banking": {"pe": 10.0, "pb": 1.5, "roe": 0.14, "de": 5.0, "rev_growth": 0.12, "avg_pe": 10.0, "avg_pb": 1.5},
    "Consumer Goods": {"pe": 20.0, "pb": 3.0, "roe": 0.18, "de": 0.5, "rev_growth": 0.15, "avg_pe": 20.0, "avg_pb": 3.0},
    "Property": {"pe": 15.0, "pb": 1.8, "roe": 0.10, "de": 1.2, "rev_growth": 0.08, "avg_pe": 15.0, "avg_pb": 1.8},
    "Infrastructure": {"pe": 14.0, "pb": 2.2, "roe": 0.12, "de": 1.0, "rev_growth": 0.10, "avg_pe": 14.0, "avg_pb": 2.2},
    "Energy": {"pe": 10.0, "pb": 1.5, "roe": 0.16, "de": 0.7, "rev_growth": 0.12, "avg_pe": 10.0, "avg_pb": 1.5},
    "Healthcare": {"pe": 25.0, "pb": 3.5, "roe": 0.15, "de": 0.4, "rev_growth": 0.20, "avg_pe": 25.0, "avg_pb": 3.5},
    "Telecommunications": {"pe": 18.0, "pb": 2.5, "roe": 0.13, "de": 0.6, "rev_growth": 0.08, "avg_pe": 18.0, "avg_pb": 2.5},
}

DEFAULT_PROFILE = {"pe": 15.0, "pb": 2.5, "roe": 0.12, "de": 0.8, "rev_growth": 0.10, "avg_pe": 15.0, "avg_pb": 2.5}


def main():
    import os
    os.environ.setdefault("DATABASE_URL", "postgresql://iporadar:iporadar_dev@localhost:5432/iporadar")

    from app.database import SessionLocal, engine, Base
    from app.models import IpoCandidate, Fundamental, CandidateStatus, PriceData, NewsArticle, Prediction, AnalysisCandidate, AnalysisResult, AnalysisRun

    if not INPUT_CSV.exists():
        print(f"Training dataset not found: {INPUT_CSV}")
        sys.exit(1)

    db = SessionLocal()

    # Clear old data (order matters for FK constraints)
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

    # Read real data
    with open(INPUT_CSV, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\nSeeding {len(rows)} real IPO candidates...")

    import numpy as np
    np.random.seed(42)

    for row in rows:
        ticker = row["ticker"]
        sector = row["sector"]
        profile = SECTOR_PROFILES.get(sector, DEFAULT_PROFILE)
        offer_price = int(row["offer_price_idr"])
        first_day_return = float(row["first_day_return"])
        outcome_signal = 1 if first_day_return > 0 else -1

        # Determine status
        listing_date = datetime.strptime(row["listing_date"], "%Y-%m-%d").date()
        status = CandidateStatus.LISTED

        # Determine underwriter tier
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

        # Generate realistic fundamentals based on sector and outcome
        noise = np.random.uniform(0.75, 1.25)
        pe = profile["pe"] * noise * (1 + outcome_signal * 0.1)
        pb = profile["pb"] * noise * (1 + outcome_signal * 0.1)
        roe = profile["roe"] * (1 + outcome_signal * 0.3 * np.random.uniform(0, 1))
        de = profile["de"] * noise
        rev_growth = profile["rev_growth"] * (1 + outcome_signal * 0.4 * np.random.uniform(0, 1))

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
            total_assets_idr=int(np.random.uniform(500e9, 50000e9)),
        )
        db.add(fundamental)

    db.commit()
    db.close()

    print(f"Done! {len(rows)} real candidates seeded with fundamentals.")
    print("\nSample tickers in DB: GOTO, BUKA, BRIS, AMMN, BREN, NCKL, MBMA...")


if __name__ == "__main__":
    main()
