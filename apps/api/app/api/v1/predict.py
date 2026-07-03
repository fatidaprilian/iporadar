from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session
from uuid import uuid4

from app.database import get_db
from app.models import IpoCandidate, Prediction
from app.ml.models import build_feature_vector, get_layer1_model, get_layer2_model

router = APIRouter()


class PredictionRequest(BaseModel):
    candidate_ids: List[str]


class PredictionResponse(BaseModel):
    prediction_ids: List[str]
    message: str


@router.post("/", response_model=PredictionResponse)
def run_predictions(request: PredictionRequest, db: Session = Depends(get_db)):
    """Triggers ML prediction pipeline for a list of candidates."""
    candidates = db.query(IpoCandidate).filter(IpoCandidate.id.in_(request.candidate_ids)).all()

    if not candidates:
        raise HTTPException(status_code=404, detail="No valid candidates found")

    prediction_ids = []

    for candidate in candidates:
        features = build_feature_vector(candidate, candidate.fundamental or {})

        sentiment_score_final = 0.0
        if candidate.news_articles:
            scores = [float(a.sentiment_score) for a in candidate.news_articles if a.sentiment_score is not None]
            if scores:
                sentiment_score_final = sum(scores) / len(scores)

        l1_model = get_layer1_model()
        l2_model = get_layer2_model()

        l1_result = l1_model.predict_proba(features)
        l2_result = l2_model.predict_proba(features)

        normalized_sentiment = (sentiment_score_final + 1.0) / 2.0
        composite_score = (l1_result["probability"] * 0.5) + (l2_result["probability"] * 0.3) + (normalized_sentiment * 0.2)

        prediction = Prediction(
            id=str(uuid4()),
            candidate_id=candidate.id,
            model_version="xgb-v1.0.0" if l1_model.model else "stub-v0.0.1",
            layer1_probability=l1_result["probability"],
            layer1_label=l1_result["label"],
            layer1_feature_importance=l1_result["feature_importance"],
            layer2_probability=l2_result["probability"],
            layer2_label=l2_result["label"],
            layer2_feature_importance=l2_result["feature_importance"],
            sentiment_score=sentiment_score_final,
            sentiment_magnitude=0.5,
            news_count=len(candidate.news_articles),
            composite_score=composite_score,
        )
        db.add(prediction)
        prediction_ids.append(prediction.id)

    db.commit()

    return PredictionResponse(
        prediction_ids=prediction_ids,
        message=f"Generated predictions for {len(prediction_ids)} candidates",
    )
