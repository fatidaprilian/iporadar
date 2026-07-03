"""IPO Candidate CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional
from datetime import date

from app.database import get_db
from app.models import IpoCandidate, CandidateStatus

router = APIRouter()


# --- Pydantic schemas ---

class FundamentalOut(BaseModel):
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    roe: Optional[float] = None
    debt_to_equity: Optional[float] = None
    total_assets_idr: Optional[int] = None
    revenue_growth_yoy: Optional[float] = None
    sector_avg_pe: Optional[float] = None
    sector_avg_pb: Optional[float] = None

    class Config:
        from_attributes = True


class CandidateOut(BaseModel):
    id: str
    ticker: str
    company_name: str
    sector: str
    listing_date: date
    offer_price_idr: int
    share_count: Optional[int] = None
    underwriter: Optional[str] = None
    underwriter_tier: Optional[int] = None
    status: str
    fundamental: Optional[FundamentalOut] = None

    class Config:
        from_attributes = True


class CreateCandidateIn(BaseModel):
    ticker: str
    company_name: str
    sector: str
    listing_date: date
    offer_price_idr: int
    share_count: Optional[int] = None
    underwriter: Optional[str] = None
    underwriter_tier: Optional[int] = None
    status: Optional[str] = CandidateStatus.UPCOMING


class UpdateCandidateIn(BaseModel):
    company_name: Optional[str] = None
    sector: Optional[str] = None
    listing_date: Optional[date] = None
    offer_price_idr: Optional[int] = None
    underwriter: Optional[str] = None
    underwriter_tier: Optional[int] = None
    status: Optional[str] = None


class PaginatedResponse(BaseModel):
    data: list[CandidateOut]
    meta: dict


# --- Endpoints ---

@router.get("/", response_model=PaginatedResponse)
def list_candidates(
    status: Optional[str] = None,
    sector: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(IpoCandidate).options(joinedload(IpoCandidate.fundamental))

    if status:
        query = query.filter(IpoCandidate.status == status)
    if sector:
        query = query.filter(IpoCandidate.sector == sector)

    total = query.count()
    candidates = (
        query.order_by(IpoCandidate.listing_date.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": candidates,
        "meta": {
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": (total + limit - 1) // limit,
        },
    }


@router.get("/{candidate_id}", response_model=CandidateOut)
def get_candidate(candidate_id: str, db: Session = Depends(get_db)):
    candidate = (
        db.query(IpoCandidate)
        .options(
            joinedload(IpoCandidate.fundamental),
            joinedload(IpoCandidate.news_articles),
            joinedload(IpoCandidate.predictions),
        )
        .filter(IpoCandidate.id == candidate_id)
        .first()
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="IPO candidate not found")
    return candidate


@router.post("/", response_model=CandidateOut, status_code=201)
def create_candidate(data: CreateCandidateIn, db: Session = Depends(get_db)):
    existing = db.query(IpoCandidate).filter(IpoCandidate.ticker == data.ticker).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Ticker {data.ticker} already exists")

    candidate = IpoCandidate(**data.model_dump())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.patch("/{candidate_id}", response_model=CandidateOut)
def update_candidate(candidate_id: str, data: UpdateCandidateIn, db: Session = Depends(get_db)):
    candidate = db.query(IpoCandidate).filter(IpoCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="IPO candidate not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(candidate, key, value)

    db.commit()
    db.refresh(candidate)
    return candidate
