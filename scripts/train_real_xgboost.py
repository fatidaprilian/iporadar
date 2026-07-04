"""Train XGBoost models on real IPO historical data.

Reads data/ipo_training_dataset.csv (real IPOs with yfinance-validated returns).
Uses real fundamentals from data/real_fundamentals.json.
Outputs: apps/api/models/layer1_xgb.pkl, layer2_xgb.pkl, sector_encoder.pkl

Usage:
    python3 scripts/train_real_xgboost.py
"""

import csv
import json
import math
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

INPUT_CSV = ROOT / "data" / "ipo_training_dataset.csv"
FUNDAMENTALS_JSON = ROOT / "data" / "real_fundamentals.json"
MODEL_DIR = ROOT / "apps" / "api" / "models"

SECTOR_PROFILES = {
    "Basic Materials": {"pe": 12.0, "pb": 2.0, "roe": 0.15, "de": 0.8, "rev_growth": 0.10},
    "Technology": {"pe": 28.0, "pb": 4.5, "roe": 0.12, "de": 0.3, "rev_growth": 0.30},
    "Financial Services": {"pe": 10.0, "pb": 1.5, "roe": 0.14, "de": 5.0, "rev_growth": 0.12},
    "Consumer Cyclical": {"pe": 22.0, "pb": 3.2, "roe": 0.16, "de": 0.5, "rev_growth": 0.18},
    "Consumer Staples": {"pe": 18.0, "pb": 2.8, "roe": 0.18, "de": 0.4, "rev_growth": 0.12},
    "Property": {"pe": 15.0, "pb": 1.8, "roe": 0.10, "de": 1.2, "rev_growth": 0.08},
    "Industrials": {"pe": 14.0, "pb": 2.2, "roe": 0.12, "de": 1.0, "rev_growth": 0.10},
    "Energy": {"pe": 10.0, "pb": 1.5, "roe": 0.16, "de": 0.7, "rev_growth": 0.12},
    "Utilities": {"pe": 16.0, "pb": 2.0, "roe": 0.11, "de": 1.5, "rev_growth": 0.06},
    "Healthcare": {"pe": 25.0, "pb": 3.5, "roe": 0.15, "de": 0.4, "rev_growth": 0.20},
    "Telecommunications": {"pe": 18.0, "pb": 2.5, "roe": 0.13, "de": 0.6, "rev_growth": 0.08},
    "Mining": {"pe": 10.0, "pb": 1.8, "roe": 0.14, "de": 0.9, "rev_growth": 0.08},
}

DEFAULT_PROFILE = {"pe": 15.0, "pb": 2.5, "roe": 0.12, "de": 0.8, "rev_growth": 0.10}


def sanitize_value(val, low, high, default):
    """Clamp a value to [low, high], returning default if None."""
    if val is None:
        return default
    return max(low, min(high, val))


def build_features(row: dict, sector_encoder: LabelEncoder, real_fundamentals: dict) -> dict:
    """Build 10-feature vector from a real IPO row using real fundamentals."""
    ticker = row["ticker"]
    sector = row["sector"]
    profile = SECTOR_PROFILES.get(sector, DEFAULT_PROFILE)
    offer_price = int(row["offer_price_idr"])
    tier = int(row["underwriter_tier"])

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

    pe_vs_sector = pe / profile["pe"] if profile["pe"] else 1.0
    pb_vs_sector = pb / profile["pb"] if profile["pb"] else 1.0

    try:
        sector_enc = sector_encoder.transform([sector])[0]
    except ValueError:
        sector_enc = 0

    return {
        "pe_ratio": round(pe, 2),
        "pb_ratio": round(pb, 2),
        "roe": round(roe, 4),
        "debt_to_equity": round(de, 4),
        "revenue_growth_yoy": round(rev_growth, 4),
        "pe_vs_sector": round(pe_vs_sector, 4),
        "pb_vs_sector": round(pb_vs_sector, 4),
        "offer_price_log": round(math.log(max(offer_price, 1)), 4),
        "underwriter_tier": tier,
        "sector_encoded": sector_enc,
    }


def main():
    np.random.seed(42)

    if not INPUT_CSV.exists():
        print(f"Training dataset not found: {INPUT_CSV}")
        print("Run scripts/build_real_dataset.py first.")
        sys.exit(1)

    if not FUNDAMENTALS_JSON.exists():
        print(f"Real fundamentals not found: {FUNDAMENTALS_JSON}")
        print("Run the yfinance fundamentals fetch script first.")
        sys.exit(1)

    with open(FUNDAMENTALS_JSON) as f:
        real_fundamentals = json.load(f)
    print(f"Loaded real fundamentals for {len(real_fundamentals)} tickers")

    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df)} real IPO records")

    df = df[df["first_day_return"].abs() < 10.0].copy()
    if "day30_return" in df.columns:
        df = df[df["day30_return"].abs() < 10.0].copy()
    print(f"After filtering outliers: {len(df)} records")

    all_sectors = list(SECTOR_PROFILES.keys())
    sector_encoder = LabelEncoder()
    sector_encoder.fit(all_sectors)

    features_list = []
    for _, row in df.iterrows():
        features_list.append(build_features(row.to_dict(), sector_encoder, real_fundamentals))

    X = pd.DataFrame(features_list)
    y_l1 = df["label_first_day"].values
    y_l2 = df["label_30day"].values

    feature_names = list(X.columns)
    print(f"\nFeatures ({len(feature_names)}): {feature_names}")
    print(f"L1 label distribution: {sum(y_l1)}/{len(y_l1)} positive ({sum(y_l1)/len(y_l1)*100:.0f}%)")
    print(f"L2 label distribution: {sum(y_l2)}/{len(y_l2)} positive ({sum(y_l2)/len(y_l2)*100:.0f}%)")

    print("\nSample features (first 5):")
    for i, (_, row) in enumerate(df.head(5).iterrows()):
        feat = features_list[i]
        print(f"  {row['ticker']}: PE={feat['pe_ratio']}, PB={feat['pb_ratio']}, "
              f"ROE={feat['roe']}, D/E={feat['debt_to_equity']}, "
              f"RevG={feat['revenue_growth_yoy']}")

    print("\n--- Training Layer 1 (First-Day Return) ---")
    l1_model = XGBClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.7,
        min_child_weight=2,
        reg_alpha=0.5,
        reg_lambda=3.0,
        gamma=0.5,
        eval_metric="logloss",
        random_state=42,
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    l1_scores = cross_val_score(l1_model, X, y_l1, cv=cv, scoring="roc_auc")
    print(f"L1 CV AUC: {l1_scores.mean():.3f} (+/- {l1_scores.std():.3f})")

    l1_model.fit(X, y_l1)

    print("\n--- Training Layer 2 (30-Day Return) ---")
    l2_model = XGBClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.7,
        min_child_weight=2,
        reg_alpha=0.5,
        reg_lambda=3.0,
        gamma=0.5,
        eval_metric="logloss",
        random_state=42,
    )

    l2_scores = cross_val_score(l2_model, X, y_l2, cv=cv, scoring="roc_auc")
    print(f"L2 CV AUC: {l2_scores.mean():.3f} (+/- {l2_scores.std():.3f})")

    l2_model.fit(X, y_l2)

    print("\n--- Feature Importance (L1) ---")
    importances = l1_model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    for i in sorted_idx[:5]:
        print(f"  {feature_names[i]}: {importances[i]:.3f}")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    with open(MODEL_DIR / "layer1_xgb.pkl", "wb") as f:
        pickle.dump({"model": l1_model.get_booster(), "feature_names": feature_names}, f)
    with open(MODEL_DIR / "layer2_xgb.pkl", "wb") as f:
        pickle.dump({"model": l2_model.get_booster(), "feature_names": feature_names}, f)
    with open(MODEL_DIR / "sector_encoder.pkl", "wb") as f:
        pickle.dump(sector_encoder, f)

    print(f"\nModels saved to {MODEL_DIR}/")
    print("  layer1_xgb.pkl")
    print("  layer2_xgb.pkl")
    print("  sector_encoder.pkl")
    print("\nDone! Re-deploy API container to pick up new models.")


if __name__ == "__main__":
    main()
