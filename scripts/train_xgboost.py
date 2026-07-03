#!/usr/bin/env python3
"""Train XGBoost models for IPO outperformance prediction.

Reads historical data from PostgreSQL, performs feature engineering,
trains Layer 1 (first-day) and Layer 2 (30-day) classifiers,
and saves models to apps/api/models/.

Usage:
  # Ensure database is seeded (run seed_historical_data.py first)
  python scripts/train_xgboost.py
  python scripts/train_xgboost.py --db-url postgresql://...
  python scripts/train_xgboost.py --folds 10
"""

import argparse
import logging
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import LabelEncoder

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "apps" / "api" / "models"
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "api"))

from app.database import Base
from app.models import Fundamental, IpoCandidate, PriceData

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://iporadar:iporadar_dev@localhost:5432/iporadar",
)

FEATURE_COLS = [
    "pe_ratio",
    "pb_ratio",
    "roe",
    "debt_to_equity",
    "revenue_growth_yoy",
    "pe_vs_sector",
    "pb_vs_sector",
    "offer_price_log",
    "underwriter_tier",
    "sector_encoded",
]


def load_data(session) -> pd.DataFrame:
    """Load candidates with fundamentals and price data from the database."""
    candidates = (
        session.query(IpoCandidate)
        .filter(IpoCandidate.status == "listed")
        .all()
    )

    rows = []
    for c in candidates:
        if not c.fundamental:
            continue

        prices = sorted(c.price_data, key=lambda p: p.date)
        if len(prices) < 2:
            continue

        f = c.fundamental
        day1_close = float(prices[0].close) if prices[0].close else None
        if day1_close is None:
            continue

        day30_close = None
        if len(prices) >= 20:
            target_idx = min(29, len(prices) - 1)
            day30_close = float(prices[target_idx].close) if prices[target_idx].close else None

        offer = c.offer_price_idr
        if not offer or offer <= 0:
            continue

        l1_label = 1 if day1_close > offer else 0
        l2_label = 1 if (day30_close and day30_close > offer) else 0

        pe = float(f.pe_ratio) if f.pe_ratio is not None else None
        pb = float(f.pb_ratio) if f.pb_ratio is not None else None
        roe = float(f.roe) if f.roe is not None else None
        de = float(f.debt_to_equity) if f.debt_to_equity is not None else None
        growth = float(f.revenue_growth_yoy) if f.revenue_growth_yoy is not None else None
        sector_avg_pe = float(f.sector_avg_pe) if f.sector_avg_pe else 15.0
        sector_avg_pb = float(f.sector_avg_pb) if f.sector_avg_pb else 2.0

        rows.append({
            "ticker": c.ticker,
            "sector": c.sector,
            "offer_price": offer,
            "underwriter_tier": c.underwriter_tier or 2,
            "pe_ratio": pe,
            "pb_ratio": pb,
            "roe": roe,
            "debt_to_equity": de,
            "revenue_growth_yoy": growth,
            "sector_avg_pe": sector_avg_pe,
            "sector_avg_pb": sector_avg_pb,
            "day1_close": day1_close,
            "day30_close": day30_close,
            "l1_label": l1_label,
            "l2_label": l2_label,
        })

    df = pd.DataFrame(rows)
    logger.info(f"Loaded {len(df)} samples from database")
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Transform raw data into feature vectors."""
    df = df.copy()

    df["pe_vs_sector"] = df["pe_ratio"] / df["sector_avg_pe"]
    df["pb_vs_sector"] = df["pb_ratio"] / df["sector_avg_pb"]
    df["offer_price_log"] = np.log1p(df["offer_price"])

    le = LabelEncoder()
    df["sector_encoded"] = le.fit_transform(df["sector"])

    for col in FEATURE_COLS:
        if col in df.columns:
            median = df[col].median()
            df[col] = df[col].fillna(median)

    return df, le


def train_model(
    X: pd.DataFrame,
    y: pd.Series,
    model_name: str,
    n_folds: int = 5,
) -> tuple[xgb.Booster, dict]:
    """Train XGBoost with stratified k-fold cross-validation."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Training {model_name}")
    logger.info(f"Samples: {len(X)} | Positive: {y.sum()} ({y.mean()*100:.1f}%) | Negative: {(~y.astype(bool)).sum()}")
    logger.info(f"{'='*60}")

    params = {
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "max_depth": 4,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 3,
        "gamma": 0.1,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "seed": 42,
    }

    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    fold_metrics = []

    for fold, (train_idx, val_idx) in enumerate(skf.split(X, y), 1):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=list(X.columns))
        dval = xgb.DMatrix(X_val, label=y_val, feature_names=list(X.columns))

        model = xgb.train(
            params,
            dtrain,
            num_boost_round=200,
            evals=[(dval, "val")],
            early_stopping_rounds=20,
            verbose_eval=False,
        )

        preds = model.predict(dval)
        pred_labels = (preds >= 0.5).astype(int)

        acc = accuracy_score(y_val, pred_labels)
        try:
            auc = roc_auc_score(y_val, preds)
        except ValueError:
            auc = 0.5

        fold_metrics.append({"fold": fold, "accuracy": acc, "auc": auc})
        logger.info(f"  Fold {fold}: Accuracy={acc:.4f}, AUC={auc:.4f}")

    mean_acc = np.mean([m["accuracy"] for m in fold_metrics])
    mean_auc = np.mean([m["auc"] for m in fold_metrics])
    logger.info(f"\nCV Results: Mean Accuracy={mean_acc:.4f}, Mean AUC={mean_auc:.4f}")

    logger.info("Training final model on full dataset...")
    dtrain_full = xgb.DMatrix(X, label=y, feature_names=list(X.columns))
    final_model = xgb.train(
        params,
        dtrain_full,
        num_boost_round=200,
        verbose_eval=False,
    )

    importance = final_model.get_score(importance_type="gain")
    if importance:
        sorted_imp = sorted(importance.items(), key=lambda x: x[1], reverse=True)
        logger.info("\nFeature Importance (gain):")
        for feat, score in sorted_imp:
            logger.info(f"  {feat:25s} {score:.4f}")

    full_preds = final_model.predict(dtrain_full)
    full_labels = (full_preds >= 0.5).astype(int)
    logger.info(f"\nFull-data classification report:")
    logger.info("\n" + classification_report(y, full_labels, target_names=["underperform", "outperform"]))

    metrics = {
        "cv_mean_accuracy": mean_acc,
        "cv_mean_auc": mean_auc,
        "fold_metrics": fold_metrics,
        "feature_importance": importance,
        "n_samples": len(X),
        "positive_rate": float(y.mean()),
    }

    return final_model, metrics


def save_model(model: xgb.Booster, feature_names: list[str], path: Path):
    """Save model in the format expected by XGBoostModelWrapper."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump({"model": model, "feature_names": feature_names}, f)
    logger.info(f"Saved model to {path}")


def main():
    parser = argparse.ArgumentParser(description="Train XGBoost models for IPO prediction")
    parser.add_argument("--db-url", default=DATABASE_URL, help="PostgreSQL connection URL")
    parser.add_argument("--folds", type=int, default=5, help="Number of CV folds")
    parser.add_argument("--output-dir", default=str(MODEL_DIR), help="Directory for model .pkl files")
    args = parser.parse_args()

    engine = create_engine(args.db_url, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        df = load_data(session)
    finally:
        session.close()

    if len(df) < 30:
        logger.error(f"Only {len(df)} samples found. Need at least 30 for meaningful training.")
        logger.error("Run scripts/seed_historical_data.py first.")
        sys.exit(1)

    df, sector_encoder = engineer_features(df)
    X = df[FEATURE_COLS]

    output_dir = Path(args.output_dir)

    l1_model, l1_metrics = train_model(X, df["l1_label"], "Layer 1 (First-Day Return)", args.folds)
    save_model(l1_model, FEATURE_COLS, output_dir / "layer1_xgb.pkl")

    has_day30 = df["day30_close"].notna()
    if has_day30.sum() >= 30:
        l2_model, l2_metrics = train_model(
            X[has_day30], df.loc[has_day30, "l2_label"],
            "Layer 2 (30-Day Return)", args.folds,
        )
        save_model(l2_model, FEATURE_COLS, output_dir / "layer2_xgb.pkl")
    else:
        logger.warning(f"Only {has_day30.sum()} samples have 30-day price data. Skipping Layer 2.")
        logger.warning("Layer 2 will use Layer 1 model as fallback.")
        save_model(l1_model, FEATURE_COLS, output_dir / "layer2_xgb.pkl")

    sector_encoder_path = output_dir / "sector_encoder.pkl"
    with open(sector_encoder_path, "wb") as f:
        pickle.dump(sector_encoder, f)
    logger.info(f"Saved sector encoder to {sector_encoder_path}")

    logger.info("\nTraining complete. Models saved to:")
    logger.info(f"  {output_dir / 'layer1_xgb.pkl'}")
    logger.info(f"  {output_dir / 'layer2_xgb.pkl'}")
    logger.info(f"  {sector_encoder_path}")


if __name__ == "__main__":
    main()
