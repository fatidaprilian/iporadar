"""Analysis orchestration endpoints — trigger, status, results.

Ported from NestJS analysis.controller.ts + analysis.service.ts + analysis.processor.ts.
Uses FastAPI BackgroundTasks instead of BullMQ + Redis.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from typing import Optional

from app.database import get_db
from app.models import (
    IpoCandidate, Prediction, AnalysisRun, AnalysisResult,
    AnalysisCandidate, CandidateStatus, RunStatus, TriggerType,
)
from app.ml.models import build_feature_vector, get_layer1_model, get_layer2_model
from app.services.prompt_builder import build_prompt

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Pydantic schemas ---

class TriggerAnalysisIn(BaseModel):
    top_n: int = 5
    candidate_ids: Optional[list[str]] = None


class AnalysisStatusOut(BaseModel):
    job_id: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class AnalysisResultOut(BaseModel):
    id: str
    job_id: str
    created_at: datetime
    candidate_count: int
    top_candidates: Optional[list] = None
    prompt: str
    status: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedResultsOut(BaseModel):
    data: list[AnalysisResultOut]
    meta: dict


# --- Background task logic ---

def _run_analysis(run_id: str, candidate_ids: Optional[list[str]], top_n: int):
    """Execute the full analysis pipeline in a background thread."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        # Mark as processing
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if not run:
            return
        run.status = RunStatus.PROCESSING
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        # Step 1: Gather candidates
        if candidate_ids:
            candidates = (
                db.query(IpoCandidate)
                .options(joinedload(IpoCandidate.fundamental), joinedload(IpoCandidate.news_articles))
                .filter(IpoCandidate.id.in_(candidate_ids))
                .all()
            )
        else:
            upcoming = (
                db.query(IpoCandidate)
                .options(joinedload(IpoCandidate.fundamental), joinedload(IpoCandidate.news_articles))
                .filter(IpoCandidate.status == CandidateStatus.UPCOMING)
                .order_by(IpoCandidate.listing_date.asc())
                .all()
            )
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc).date() - timedelta(days=90)
            recent = (
                db.query(IpoCandidate)
                .options(joinedload(IpoCandidate.fundamental), joinedload(IpoCandidate.news_articles))
                .filter(
                    IpoCandidate.status == CandidateStatus.LISTED,
                    IpoCandidate.listing_date >= cutoff,
                )
                .order_by(IpoCandidate.listing_date.desc())
                .limit(20)
                .all()
            )
            seen = set()
            candidates = []
            for c in [*upcoming, *recent]:
                if c.id not in seen:
                    seen.add(c.id)
                    candidates.append(c)

        if not candidates:
            run.status = RunStatus.FAILED
            run.error_message = "No candidates found for analysis"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        logger.info(f"Found {len(candidates)} candidates for analysis run {run_id}")

        # Step 2: Run ML predictions
        l1_model = get_layer1_model()
        l2_model = get_layer2_model()
        saved_predictions: list[Prediction] = []

        for c in candidates:
            features = build_feature_vector(c, c.fundamental or {})

            sentiment_final = 0.0
            if c.news_articles:
                scores = [float(a.sentiment_score) for a in c.news_articles if a.sentiment_score is not None]
                if scores:
                    sentiment_final = sum(scores) / len(scores)

            l1_result = l1_model.predict_proba(features)
            l2_result = l2_model.predict_proba(features)

            normalized_sentiment = (sentiment_final + 1.0) / 2.0
            composite = (l1_result["probability"] * 0.5) + (l2_result["probability"] * 0.3) + (normalized_sentiment * 0.2)

            pred = Prediction(
                candidate_id=c.id,
                model_version="xgb-v1.0.0" if l1_model.model else "stub-v0.0.1",
                layer1_probability=l1_result["probability"],
                layer1_label=l1_result["label"],
                layer1_feature_importance=l1_result["feature_importance"],
                layer2_probability=l2_result["probability"],
                layer2_label=l2_result["label"],
                layer2_feature_importance=l2_result["feature_importance"],
                sentiment_score=sentiment_final,
                sentiment_magnitude=0.5,
                news_count=len(c.news_articles) if c.news_articles else 0,
                composite_score=composite,
            )
            db.add(pred)
            db.flush()
            saved_predictions.append(pred)

        # Step 3: Rank by composite score, take top N
        ranked = sorted(
            [p for p in saved_predictions if p.composite_score is not None],
            key=lambda p: float(p.composite_score),
            reverse=True,
        )[:top_n]

        # Step 4: Save analysis candidates
        for i, pred in enumerate(ranked):
            ac = AnalysisCandidate(
                run_id=run_id,
                candidate_id=pred.candidate_id,
                prediction_id=pred.id,
                composite_rank=i + 1,
            )
            db.add(ac)

        # Step 5: Build prompt
        candidate_map = {c.id: c for c in candidates}
        ranked_with_candidates = [
            {
                "candidate": candidate_map[pred.candidate_id],
                "prediction": pred,
                "rank": i + 1,
            }
            for i, pred in enumerate(ranked)
        ]

        prompt = build_prompt(ranked_with_candidates, datetime.now(timezone.utc))

        # Step 6: Save result
        top_summary = [
            {
                "ticker": rc["candidate"].ticker,
                "companyName": rc["candidate"].company_name,
                "compositeRank": rc["rank"],
                "layer1Score": str(rc["prediction"].layer1_probability),
                "layer2Score": str(rc["prediction"].layer2_probability),
                "sentimentScore": str(rc["prediction"].sentiment_score),
            }
            for rc in ranked_with_candidates
        ]

        result = AnalysisResult(
            run_id=run_id,
            candidate_count=len(candidates),
            prompt=prompt,
            top_candidates_summary=top_summary,
        )
        db.add(result)

        run.status = RunStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Analysis run {run_id} completed. {len(ranked)} candidates ranked.")

    except Exception as e:
        logger.error(f"Analysis run {run_id} failed: {e}")
        try:
            run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
            if run:
                run.status = RunStatus.FAILED
                run.error_message = str(e)
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# --- Endpoints ---

@router.post("/trigger")
def trigger_analysis(
    data: TriggerAnalysisIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    run = AnalysisRun(
        status=RunStatus.QUEUED,
        top_n=data.top_n,
        trigger_type=TriggerType.MANUAL,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(_run_analysis, run.id, data.candidate_ids, data.top_n)

    return {
        "jobId": run.id,
        "status": run.status,
        "message": "Analysis job queued",
    }


@router.get("/{job_id}", response_model=AnalysisStatusOut)
def get_run_status(job_id: str, db: Session = Depends(get_db)):
    run = db.query(AnalysisRun).filter(AnalysisRun.id == job_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    return AnalysisStatusOut(
        job_id=run.id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
    )


@router.get("/results/list", response_model=PaginatedResultsOut)
def list_results(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(AnalysisResult).options(joinedload(AnalysisResult.run))
    total = query.count()
    results = (
        query.order_by(AnalysisResult.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    data = [
        AnalysisResultOut(
            id=r.id,
            job_id=r.run_id,
            created_at=r.created_at,
            candidate_count=r.candidate_count,
            top_candidates=r.top_candidates_summary,
            prompt=r.prompt,
            status=r.run.status if r.run else None,
        )
        for r in results
    ]

    return {
        "data": data,
        "meta": {
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": (total + limit - 1) // limit,
        },
    }


@router.get("/results/{result_id}", response_model=AnalysisResultOut)
def get_result(result_id: str, db: Session = Depends(get_db)):
    result = (
        db.query(AnalysisResult)
        .options(joinedload(AnalysisResult.run))
        .filter(AnalysisResult.id == result_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Analysis result not found")

    return AnalysisResultOut(
        id=result.id,
        job_id=result.run_id,
        created_at=result.created_at,
        candidate_count=result.candidate_count,
        top_candidates=result.top_candidates_summary,
        prompt=result.prompt,
        status=result.run.status if result.run else None,
    )
