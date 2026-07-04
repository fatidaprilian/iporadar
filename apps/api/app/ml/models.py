import logging
import math
import os
import pickle

import numpy as np
import pandas as pd
import xgboost as xgb

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "models")

SECTOR_PROFILES = {
    "Basic Materials": {"sector_avg_pe": 12.0, "sector_avg_pb": 2.0},
    "Technology": {"sector_avg_pe": 28.0, "sector_avg_pb": 4.5},
    "Financial Services": {"sector_avg_pe": 10.0, "sector_avg_pb": 1.5},
    "Consumer Cyclical": {"sector_avg_pe": 22.0, "sector_avg_pb": 3.2},
    "Consumer Staples": {"sector_avg_pe": 18.0, "sector_avg_pb": 2.8},
    "Property": {"sector_avg_pe": 15.0, "sector_avg_pb": 1.8},
    "Industrials": {"sector_avg_pe": 14.0, "sector_avg_pb": 2.2},
    "Energy": {"sector_avg_pe": 10.0, "sector_avg_pb": 1.5},
    "Utilities": {"sector_avg_pe": 16.0, "sector_avg_pb": 2.0},
    "Healthcare": {"sector_avg_pe": 25.0, "sector_avg_pb": 3.5},
    "Telecommunications": {"sector_avg_pe": 18.0, "sector_avg_pb": 2.5},
    "Mining": {"sector_avg_pe": 10.0, "sector_avg_pb": 1.8},
}


def _load_sector_encoder():
    path = os.path.join(MODEL_DIR, "sector_encoder.pkl")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return None


_sector_encoder = _load_sector_encoder()


def build_feature_vector(candidate, fundamental) -> dict:
    """Build the feature dict expected by the trained XGBoost models.

    Accepts either ORM objects or plain dicts.
    """
    if hasattr(candidate, "__dict__"):
        sector = candidate.sector or "Industrials"
        offer_price = candidate.offer_price_idr or 0
        uw_tier = candidate.underwriter_tier or 2
    else:
        sector = candidate.get("sector", "Industrials")
        offer_price = candidate.get("offer_price_idr", 0)
        uw_tier = candidate.get("underwriter_tier", 2)

    if hasattr(fundamental, "__dict__"):
        pe = float(fundamental.pe_ratio) if fundamental.pe_ratio is not None else 15.0
        pb = float(fundamental.pb_ratio) if fundamental.pb_ratio is not None else 2.0
        roe = float(fundamental.roe) if fundamental.roe is not None else 0.1
        de = float(fundamental.debt_to_equity) if fundamental.debt_to_equity is not None else 0.5
        growth = float(fundamental.revenue_growth_yoy) if fundamental.revenue_growth_yoy is not None else 0.0
        s_pe = float(fundamental.sector_avg_pe) if fundamental.sector_avg_pe else None
        s_pb = float(fundamental.sector_avg_pb) if fundamental.sector_avg_pb else None
    else:
        pe = fundamental.get("pe_ratio", 15.0) or 15.0
        pb = fundamental.get("pb_ratio", 2.0) or 2.0
        roe = fundamental.get("roe", 0.1) or 0.1
        de = fundamental.get("debt_to_equity", 0.5) or 0.5
        growth = fundamental.get("revenue_growth_yoy", 0.0) or 0.0
        s_pe = fundamental.get("sector_avg_pe")
        s_pb = fundamental.get("sector_avg_pb")

    profile = SECTOR_PROFILES.get(sector, SECTOR_PROFILES["Industrials"])
    sector_avg_pe = s_pe or profile["sector_avg_pe"]
    sector_avg_pb = s_pb or profile["sector_avg_pb"]

    pe_vs_sector = pe / sector_avg_pe if sector_avg_pe else 1.0
    pb_vs_sector = pb / sector_avg_pb if sector_avg_pb else 1.0
    offer_price_log = math.log(max(offer_price, 1))

    sector_encoded = 0
    if _sector_encoder is not None:
        try:
            sector_encoded = int(_sector_encoder.transform([sector])[0])
        except ValueError:
            sector_encoded = 0

    return {
        "pe_ratio": pe,
        "pb_ratio": pb,
        "roe": roe,
        "debt_to_equity": de,
        "revenue_growth_yoy": growth,
        "pe_vs_sector": pe_vs_sector,
        "pb_vs_sector": pb_vs_sector,
        "offer_price_log": offer_price_log,
        "underwriter_tier": uw_tier,
        "sector_encoded": sector_encoded,
    }


class XGBoostModelWrapper:
    def __init__(self, model_path: str, model_type: str = "classifier"):
        self.model_path = model_path
        self.model_type = model_type
        self.model = None
        self.feature_names = []

    def load(self):
        if not os.path.exists(self.model_path):
            logger.warning(f"Model file {self.model_path} not found. Running in dummy mode.")
            return False

        try:
            with open(self.model_path, "rb") as f:
                saved_data = pickle.load(f)
                self.model = saved_data["model"]
                self.feature_names = saved_data["feature_names"]
            logger.info(f"Loaded {self.model_type} model from {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def predict_proba(self, features: dict) -> dict:
        """Returns probability of outperforming the market."""
        if self.model is None:
            return self._dummy_predict(features)

        df = pd.DataFrame([features])

        for col in self.feature_names:
            if col not in df.columns:
                df[col] = 0.0

        df = df[self.feature_names]

        try:
            dmatrix = xgb.DMatrix(df, feature_names=self.feature_names)
            probs = self.model.predict(dmatrix)
            prob_outperform = float(probs[0])

            importance = self.model.get_score(importance_type="gain")
            top_features = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5])

            return {
                "probability": prob_outperform,
                "label": "outperform" if prob_outperform >= 0.5 else "underperform",
                "feature_importance": top_features,
            }
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return self._dummy_predict(features)

    def _dummy_predict(self, features: dict) -> dict:
        """Fallback heuristics if no model is trained."""
        prob = 0.5
        roe = features.get("roe", 0)
        sentiment = features.get("sentiment_score", 0)

        if roe > 0.15:
            prob += 0.15
        if sentiment > 0.3:
            prob += 0.15
        if sentiment < -0.3:
            prob -= 0.15

        prob = max(0.01, min(0.99, prob))

        return {
            "probability": prob,
            "label": "outperform" if prob >= 0.5 else "underperform",
            "feature_importance": {
                "roe": 0.4 if roe > 0 else 0,
                "sentiment_score": 0.6 if sentiment != 0 else 0,
            },
        }


layer1_model = XGBoostModelWrapper(os.path.join(MODEL_DIR, "layer1_xgb.pkl"))
layer2_model = XGBoostModelWrapper(os.path.join(MODEL_DIR, "layer2_xgb.pkl"))

layer1_model.load()
layer2_model.load()


def get_layer1_model():
    return layer1_model


def get_layer2_model():
    return layer2_model
