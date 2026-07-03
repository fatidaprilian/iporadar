#!/usr/bin/env python3
"""Seed database with historical IPO data for ML training.

Two modes:
  --real   Read scripts/data/ipo_list.csv, fetch yfinance prices, mock fundamentals.
  default  Generate ~300 synthetic but realistic BEI IPO samples.

Real mode fetches actual price action from Yahoo Finance for label computation
(first-day return, 30-day return). Fundamentals are simulated per sector profile
because historical IPO-time fundamentals are not publicly available via free APIs.

Usage:
  # Ensure PostgreSQL is running (docker compose up postgres)
  python scripts/seed_historical_data.py               # synthetic mode
  python scripts/seed_historical_data.py --real         # real + synthetic supplement
  python scripts/seed_historical_data.py --count 200    # custom sample count
"""

import argparse
import csv
import logging
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "api"))

from app.database import Base
from app.models import CandidateStatus, Fundamental, IpoCandidate, PriceData

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://iporadar:iporadar_dev@localhost:5432/iporadar",
)
RANDOM_SEED = 42

SECTOR_PROFILES = {
    "Mining": {
        "pe": (6, 18), "pb": (0.8, 3.5), "roe": (0.08, 0.25),
        "de": (0.3, 1.5), "growth": (-0.05, 0.30), "weight": 0.20,
        "sector_avg_pe": 12.0, "sector_avg_pb": 2.0,
    },
    "Technology": {
        "pe": (15, 50), "pb": (2.0, 8.0), "roe": (0.03, 0.18),
        "de": (0.1, 0.8), "growth": (0.10, 0.50), "weight": 0.10,
        "sector_avg_pe": 28.0, "sector_avg_pb": 4.5,
    },
    "Banking": {
        "pe": (7, 15), "pb": (0.7, 2.5), "roe": (0.08, 0.20),
        "de": (4.0, 9.0), "growth": (0.03, 0.18), "weight": 0.12,
        "sector_avg_pe": 11.0, "sector_avg_pb": 1.5,
    },
    "Consumer": {
        "pe": (12, 30), "pb": (1.5, 5.0), "roe": (0.10, 0.28),
        "de": (0.2, 1.2), "growth": (0.03, 0.25), "weight": 0.15,
        "sector_avg_pe": 20.0, "sector_avg_pb": 3.0,
    },
    "Property": {
        "pe": (6, 18), "pb": (0.4, 2.0), "roe": (0.04, 0.15),
        "de": (0.5, 2.5), "growth": (-0.08, 0.15), "weight": 0.10,
        "sector_avg_pe": 12.0, "sector_avg_pb": 1.2,
    },
    "Healthcare": {
        "pe": (15, 35), "pb": (2.0, 6.0), "roe": (0.10, 0.25),
        "de": (0.2, 1.0), "growth": (0.08, 0.35), "weight": 0.07,
        "sector_avg_pe": 24.0, "sector_avg_pb": 3.5,
    },
    "Industrial": {
        "pe": (7, 18), "pb": (0.7, 3.0), "roe": (0.05, 0.18),
        "de": (0.4, 2.0), "growth": (-0.03, 0.20), "weight": 0.13,
        "sector_avg_pe": 13.0, "sector_avg_pb": 1.8,
    },
    "Infrastructure": {
        "pe": (10, 25), "pb": (1.0, 3.5), "roe": (0.06, 0.18),
        "de": (0.5, 2.5), "growth": (0.03, 0.22), "weight": 0.08,
        "sector_avg_pe": 16.0, "sector_avg_pb": 2.2,
    },
    "Energy": {
        "pe": (5, 14), "pb": (0.6, 2.5), "roe": (0.08, 0.22),
        "de": (0.3, 1.8), "growth": (-0.05, 0.25), "weight": 0.05,
        "sector_avg_pe": 9.0, "sector_avg_pb": 1.5,
    },
}

SECTORS = list(SECTOR_PROFILES.keys())
SECTOR_WEIGHTS = [SECTOR_PROFILES[s]["weight"] for s in SECTORS]

UNDERWRITER_TIERS = {
    1: ["Mandiri Sekuritas", "BCA Sekuritas", "BRI Danareksa", "Indo Premier"],
    2: ["Mirae Asset", "CGS-CIMB", "Sinarmas Sekuritas", "MNC Sekuritas"],
    3: ["Jasa Utama Capital", "Erdikha Elit", "Pacific Sekuritas", "Victoria Sekuritas"],
}


def _rand_uniform(rng: np.random.Generator, lo: float, hi: float) -> float:
    return float(rng.uniform(lo, hi))


def _generate_mock_fundamental(rng: np.random.Generator, sector: str) -> dict:
    p = SECTOR_PROFILES[sector]
    pe = round(_rand_uniform(rng, *p["pe"]), 2)
    pb = round(_rand_uniform(rng, *p["pb"]), 2)
    roe = round(_rand_uniform(rng, *p["roe"]), 4)
    de = round(_rand_uniform(rng, *p["de"]), 4)
    growth = round(_rand_uniform(rng, *p["growth"]), 4)
    revenue = int(rng.integers(50_000_000_000, 5_000_000_000_000))
    net_income = int(revenue * roe * _rand_uniform(rng, 0.6, 1.4))
    total_assets = int(revenue * _rand_uniform(rng, 1.5, 5.0))
    return {
        "pe_ratio": pe,
        "pb_ratio": pb,
        "roe": roe,
        "debt_to_equity": de,
        "revenue_growth_yoy": growth,
        "revenue_idr": revenue,
        "net_income_idr": net_income,
        "total_assets_idr": total_assets,
        "sector_avg_pe": p["sector_avg_pe"],
        "sector_avg_pb": p["sector_avg_pb"],
    }


def _compute_first_day_label(fundamental: dict) -> int:
    """Probabilistic label correlated with fundamentals (for synthetic data)."""
    rng = np.random.default_rng()
    score = 0.0
    pe_vs_sector = fundamental["pe_ratio"] / fundamental["sector_avg_pe"]
    if pe_vs_sector < 0.8:
        score += 0.15
    elif pe_vs_sector > 1.5:
        score -= 0.15
    if fundamental["roe"] > 0.15:
        score += 0.15
    if fundamental["revenue_growth_yoy"] > 0.15:
        score += 0.10
    if fundamental["debt_to_equity"] > 2.5:
        score -= 0.10
    prob = 0.55 + score + rng.normal(0, 0.08)
    return 1 if rng.random() < np.clip(prob, 0.15, 0.90) else 0


def _compute_30day_label(first_day_label: int, fundamental: dict) -> int:
    rng = np.random.default_rng()
    base = 0.45
    if first_day_label == 1:
        base += 0.08
    if fundamental["roe"] > 0.15:
        base += 0.10
    if fundamental["revenue_growth_yoy"] > 0.10:
        base += 0.08
    prob = base + rng.normal(0, 0.10)
    return 1 if rng.random() < np.clip(prob, 0.15, 0.85) else 0


def _generate_price_series(
    rng: np.random.Generator,
    offer_price: int,
    listing_date: date,
    first_day_label: int,
    thirty_day_label: int,
    days: int = 35,
) -> list[dict]:
    """Generate synthetic OHLCV data for a given number of trading days."""
    if first_day_label == 1:
        day1_return = abs(rng.normal(0.12, 0.08))
    else:
        day1_return = -abs(rng.normal(0.05, 0.06))

    day1_close = max(offer_price * (1 + day1_return), offer_price * 0.65)

    if thirty_day_label == 1:
        drift = abs(rng.normal(0.003, 0.002))
    else:
        drift = -abs(rng.normal(0.002, 0.002))

    prices = []
    current = day1_close
    trading_day = listing_date

    for i in range(days):
        if i == 0:
            open_p = offer_price * (1 + rng.normal(day1_return * 0.7, 0.02))
            close_p = day1_close
        else:
            daily_return = drift + rng.normal(0, 0.025)
            current = current * (1 + daily_return)
            current = max(current, offer_price * 0.30)
            open_p = current * (1 + rng.normal(0, 0.008))
            close_p = current

        high_p = max(open_p, close_p) * (1 + abs(rng.normal(0.01, 0.008)))
        low_p = min(open_p, close_p) * (1 - abs(rng.normal(0.01, 0.008)))
        volume = int(rng.integers(500_000, 50_000_000))

        prices.append({
            "date": trading_day,
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": volume,
        })

        skip = 1
        if trading_day.weekday() == 4:
            skip = 3
        trading_day = trading_day + timedelta(days=skip)

    return prices


def _generate_synthetic_ticker(rng: np.random.Generator, index: int) -> str:
    """Generate a 4-letter ticker that looks like a BEI code."""
    consonants = "BCDFGHJKLMNPQRSTVWXYZ"
    vowels = "AEIOU"
    t = (
        rng.choice(list(consonants))
        + rng.choice(list(vowels))
        + rng.choice(list(consonants))
        + rng.choice(list(consonants + vowels))
    )
    return t


def _generate_company_name(rng: np.random.Generator, sector: str, ticker: str) -> str:
    prefixes = {
        "Mining": ["Mineral", "Bumi", "Tambang", "Logam"],
        "Technology": ["Digital", "Tekno", "Cyber", "Data"],
        "Banking": ["Bank", "Dana", "Kredit", "Modal"],
        "Consumer": ["Ritel", "Niaga", "Perdagangan", "Konsumer"],
        "Property": ["Graha", "Properti", "Bangun", "Cipta"],
        "Healthcare": ["Medika", "Sehat", "Farma", "Klinik"],
        "Industrial": ["Industri", "Pabrik", "Manufaktur", "Karya"],
        "Infrastructure": ["Infra", "Jalan", "Konstruksi", "Sarana"],
        "Energy": ["Energi", "Listrik", "Solar", "Daya"],
    }
    suffixes = ["Nusantara", "Indonesia", "Jaya", "Sejahtera", "Mandiri", "Global", "Prima", "Abadi"]
    prefix = rng.choice(prefixes.get(sector, ["Indo"]))
    suffix = rng.choice(suffixes)
    return f"PT {prefix} {suffix} Tbk"


def seed_synthetic(session, count: int):
    rng = np.random.default_rng(RANDOM_SEED)
    created = 0
    used_tickers = set()

    existing = {r[0] for r in session.query(IpoCandidate.ticker).all()}
    used_tickers.update(existing)

    for i in range(count * 2):
        if created >= count:
            break

        ticker = _generate_synthetic_ticker(rng, i)
        if ticker in used_tickers:
            continue
        used_tickers.add(ticker)

        sector = rng.choice(SECTORS, p=SECTOR_WEIGHTS)
        year = int(rng.choice([2019, 2020, 2021, 2022, 2023, 2024], p=[0.10, 0.12, 0.15, 0.18, 0.25, 0.20]))
        month = int(rng.integers(1, 13))
        day = int(rng.integers(1, 28))
        listing_date = date(year, month, day)
        if listing_date.weekday() >= 5:
            listing_date = listing_date + timedelta(days=(7 - listing_date.weekday()))

        offer_price = int(rng.choice([100, 110, 120, 150, 180, 200, 250, 300, 350, 400, 500, 750, 1000, 1500, 2000, 3000]))

        tier = int(rng.choice([1, 2, 3], p=[0.25, 0.45, 0.30]))
        uw_name = rng.choice(UNDERWRITER_TIERS[tier])
        share_count = int(rng.integers(100_000_000, 5_000_000_000))

        fundamentals = _generate_mock_fundamental(rng, sector)
        l1_label = _compute_first_day_label(fundamentals)
        l2_label = _compute_30day_label(l1_label, fundamentals)
        price_series = _generate_price_series(rng, offer_price, listing_date, l1_label, l2_label)

        candidate = IpoCandidate(
            id=str(uuid.uuid4()),
            ticker=ticker,
            company_name=_generate_company_name(rng, sector, ticker),
            sector=sector,
            listing_date=listing_date,
            offer_price_idr=offer_price,
            share_count=share_count,
            underwriter=uw_name,
            underwriter_tier=tier,
            status=CandidateStatus.LISTED,
        )
        session.add(candidate)
        session.flush()

        fund = Fundamental(
            id=str(uuid.uuid4()),
            candidate_id=candidate.id,
            pe_ratio=fundamentals["pe_ratio"],
            pb_ratio=fundamentals["pb_ratio"],
            roe=fundamentals["roe"],
            debt_to_equity=fundamentals["debt_to_equity"],
            total_assets_idr=fundamentals["total_assets_idr"],
            revenue_idr=fundamentals["revenue_idr"],
            net_income_idr=fundamentals["net_income_idr"],
            revenue_growth_yoy=fundamentals["revenue_growth_yoy"],
            sector_avg_pe=fundamentals["sector_avg_pe"],
            sector_avg_pb=fundamentals["sector_avg_pb"],
            report_date=datetime(year, 1, 1, tzinfo=timezone.utc),
        )
        session.add(fund)

        for p in price_series:
            pd_record = PriceData(
                id=str(uuid.uuid4()),
                candidate_id=candidate.id,
                date=p["date"],
                open=p["open"],
                high=p["high"],
                low=p["low"],
                close=p["close"],
                volume=p["volume"],
            )
            session.add(pd_record)

        created += 1
        if created % 50 == 0:
            logger.info(f"  Generated {created}/{count} synthetic samples")

    session.commit()
    logger.info(f"Seeded {created} synthetic IPO samples")
    return created


def seed_real(session, csv_path: str, target: int):
    """Seed from CSV with real yfinance price data + mock fundamentals."""
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        return 0

    rng = np.random.default_rng(RANDOM_SEED)

    if not os.path.exists(csv_path):
        logger.error(f"CSV not found: {csv_path}")
        return 0

    existing = {r[0] for r in session.query(IpoCandidate.ticker).all()}
    created = 0

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info(f"Processing {len(rows)} tickers from {csv_path}")

    for row in rows:
        ticker = row["ticker"].strip().upper()
        if ticker in existing:
            logger.info(f"  {ticker} already exists, skipping")
            continue

        sector = row.get("sector", "Industrial").strip()
        if sector not in SECTOR_PROFILES:
            sector = "Industrial"

        listing_str = row.get("listing_date", "").strip()
        try:
            listing_date = date.fromisoformat(listing_str)
        except ValueError:
            logger.warning(f"  {ticker}: invalid listing_date '{listing_str}', skipping")
            continue

        try:
            offer_price = int(row.get("offer_price_idr", 0))
        except ValueError:
            offer_price = 0
        if offer_price <= 0:
            logger.warning(f"  {ticker}: invalid offer_price, skipping")
            continue

        symbol = f"{ticker}.JK"
        start = listing_date - timedelta(days=1)
        end = listing_date + timedelta(days=50)
        try:
            hist = yf.download(symbol, start=str(start), end=str(end), progress=False, timeout=10)
        except Exception as e:
            logger.warning(f"  {ticker}: yfinance error: {e}")
            continue

        if hist.empty or len(hist) < 2:
            logger.warning(f"  {ticker}: no price data from yfinance, skipping")
            continue

        logger.info(f"  {ticker}: fetched {len(hist)} price records")

        candidate = IpoCandidate(
            id=str(uuid.uuid4()),
            ticker=ticker,
            company_name=row.get("company_name", f"PT {ticker} Tbk").strip(),
            sector=sector,
            listing_date=listing_date,
            offer_price_idr=offer_price,
            share_count=int(row.get("share_count", 0)) or None,
            underwriter=row.get("underwriter", "").strip() or None,
            underwriter_tier=int(row.get("underwriter_tier", 0)) or None,
            status=CandidateStatus.LISTED,
        )
        session.add(candidate)
        session.flush()

        fundamentals = _generate_mock_fundamental(rng, sector)
        fund = Fundamental(
            id=str(uuid.uuid4()),
            candidate_id=candidate.id,
            pe_ratio=fundamentals["pe_ratio"],
            pb_ratio=fundamentals["pb_ratio"],
            roe=fundamentals["roe"],
            debt_to_equity=fundamentals["debt_to_equity"],
            total_assets_idr=fundamentals["total_assets_idr"],
            revenue_idr=fundamentals["revenue_idr"],
            net_income_idr=fundamentals["net_income_idr"],
            revenue_growth_yoy=fundamentals["revenue_growth_yoy"],
            sector_avg_pe=fundamentals["sector_avg_pe"],
            sector_avg_pb=fundamentals["sector_avg_pb"],
            report_date=datetime(listing_date.year, 1, 1, tzinfo=timezone.utc),
        )
        session.add(fund)

        for idx_row in hist.itertuples():
            row_date = idx_row.Index
            if hasattr(row_date, "date"):
                row_date = row_date.date()
            pd_record = PriceData(
                id=str(uuid.uuid4()),
                candidate_id=candidate.id,
                date=row_date,
                open=round(float(idx_row.Open), 2),
                high=round(float(idx_row.High), 2),
                low=round(float(idx_row.Low), 2),
                close=round(float(idx_row.Close), 2),
                volume=int(idx_row.Volume),
            )
            session.add(pd_record)

        created += 1
        existing.add(ticker)

    session.commit()
    logger.info(f"Seeded {created} real IPO samples from CSV")

    remaining = target - created
    if remaining > 0:
        logger.info(f"Supplementing with {remaining} synthetic samples to reach {target}")
        created += seed_synthetic(session, remaining)

    return created


def main():
    parser = argparse.ArgumentParser(description="Seed historical IPO data for ML training")
    parser.add_argument("--real", action="store_true", help="Use CSV + yfinance (real price data)")
    parser.add_argument("--csv", default=str(PROJECT_ROOT / "scripts" / "data" / "ipo_list.csv"),
                        help="Path to IPO list CSV (for --real mode)")
    parser.add_argument("--count", type=int, default=300, help="Target sample count")
    parser.add_argument("--db-url", default=DATABASE_URL, help="PostgreSQL connection URL")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables before seeding")
    args = parser.parse_args()

    engine = create_engine(args.db_url, echo=False)
    if args.reset:
        logger.warning("Dropping all tables and recreating...")
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        existing_count = session.query(IpoCandidate).count()
        if existing_count > 0 and not args.reset:
            logger.info(f"Database already has {existing_count} candidates. Use --reset to start fresh.")
            return

        if args.real:
            total = seed_real(session, args.csv, args.count)
        else:
            total = seed_synthetic(session, args.count)

        final_count = session.query(IpoCandidate).count()
        logger.info(f"Done. Total candidates in database: {final_count}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
