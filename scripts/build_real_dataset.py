"""Validate IPO CSV against yfinance and generate training-ready dataset.

Reads data/ipo_historical_bei.csv, fetches actual prices from yfinance,
calculates first-day and 30-day returns, and outputs the enriched CSV.

Usage:
    python3 scripts/build_real_dataset.py
"""

import csv
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add project root for imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

INPUT_CSV = ROOT / "data" / "ipo_historical_bei.csv"
OUTPUT_CSV = ROOT / "data" / "ipo_training_dataset.csv"


def fetch_price_data(ticker_jk: str, listing_date: str, offer_price: int):
    """Fetch first-day and 30-day closing prices from yfinance."""
    import yfinance as yf
    import pandas as pd

    ld = datetime.strptime(listing_date, "%Y-%m-%d")
    start = ld - timedelta(days=1)
    end = ld + timedelta(days=45)

    try:
        hist = yf.download(ticker_jk, start=start.strftime("%Y-%m-%d"),
                           end=end.strftime("%Y-%m-%d"), progress=False, timeout=10)
    except Exception as e:
        print(f"  ERROR fetching {ticker_jk}: {e}")
        return None, None, None, None

    if hist.empty:
        return None, None, None, None

    if isinstance(hist.columns, pd.MultiIndex):
        hist.columns = hist.columns.get_level_values(0)

    hist = hist.sort_index()

    first_day_close = None
    day30_close = None

    if len(hist) > 0:
        first_day_close = float(hist.iloc[0]["Close"])

    target_30 = ld + timedelta(days=30)
    mask_30 = hist.index <= pd.Timestamp(target_30)
    if mask_30.any():
        day30_close = float(hist[mask_30].iloc[-1]["Close"])

    first_day_return = None
    day30_return = None

    if first_day_close and offer_price > 0:
        first_day_return = (first_day_close - offer_price) / offer_price

    if day30_close and offer_price > 0:
        day30_return = (day30_close - offer_price) / offer_price

    return first_day_close, day30_close, first_day_return, day30_return


def main():
    import yfinance  # noqa: ensure importable

    if not INPUT_CSV.exists():
        print(f"Input CSV not found: {INPUT_CSV}")
        sys.exit(1)

    with open(INPUT_CSV, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} IPO records from {INPUT_CSV}")
    print("Fetching price data from yfinance...\n")

    enriched = []
    valid = 0
    skipped = 0

    for i, row in enumerate(rows):
        ticker = row["ticker"]
        ticker_jk = f"{ticker}.JK"
        listing_date = row["listing_date"]
        offer_price = int(row["offer_price_idr"])

        print(f"[{i+1}/{len(rows)}] {ticker_jk} (listed {listing_date}, offer Rp{offer_price:,})...", end=" ")

        fd_close, d30_close, fd_return, d30_return = fetch_price_data(
            ticker_jk, listing_date, offer_price
        )

        if fd_return is None:
            print("SKIP (no price data)")
            skipped += 1
            continue

        label_first_day = 1 if fd_return > 0 else 0
        label_30day = 1 if (d30_return or 0) > 0 else 0

        enriched_row = {
            **row,
            "first_day_close": round(fd_close, 2) if fd_close else "",
            "day30_close": round(d30_close, 2) if d30_close else "",
            "first_day_return": round(fd_return, 4) if fd_return is not None else "",
            "day30_return": round(d30_return, 4) if d30_return is not None else "",
            "label_first_day": label_first_day,
            "label_30day": label_30day,
        }
        enriched.append(enriched_row)
        valid += 1

        sign_fd = "+" if fd_return > 0 else ""
        sign_30 = "+" if (d30_return or 0) > 0 else ""
        print(f"OK  fd={sign_fd}{fd_return:.1%}  30d={sign_30}{d30_return:.1%}" if d30_return else f"OK  fd={sign_fd}{fd_return:.1%}")

        time.sleep(0.3)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    if enriched:
        fieldnames = list(enriched[0].keys())
        with open(OUTPUT_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(enriched)

    print(f"\nDone. {valid} valid, {skipped} skipped.")
    print(f"Training dataset saved to: {OUTPUT_CSV}")

    positive_fd = sum(1 for r in enriched if r["label_first_day"] == 1)
    positive_30 = sum(1 for r in enriched if r["label_30day"] == 1)
    print(f"\nLabel distribution:")
    print(f"  First-day outperform: {positive_fd}/{valid} ({positive_fd/valid*100:.0f}%)")
    print(f"  30-day outperform:    {positive_30}/{valid} ({positive_30/valid*100:.0f}%)")


if __name__ == "__main__":
    main()
