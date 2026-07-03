"""SQLAlchemy ORM models — full schema matching the PostgreSQL tables."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, BigInteger, SmallInteger, DateTime, JSON,
    ForeignKey, Numeric, Date, Text, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# --- Enums ---

class CandidateStatus:
    UPCOMING = "upcoming"
    LISTED = "listed"
    DELISTED = "delisted"


class RunStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TriggerType:
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class SentimentLabel:
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


# --- Models ---

class IpoCandidate(Base):
    __tablename__ = "ipo_candidate"

    id = Column(String, primary_key=True, default=_uuid)
    ticker = Column(String, unique=True, index=True, nullable=False)
    company_name = Column(String, nullable=False)
    sector = Column(String, index=True, nullable=False)
    listing_date = Column(Date, index=True, nullable=False)
    offer_price_idr = Column(Integer, nullable=False)
    share_count = Column(BigInteger, nullable=True)
    underwriter = Column(String, nullable=True)
    underwriter_tier = Column(SmallInteger, nullable=True)
    status = Column(String, index=True, default=CandidateStatus.UPCOMING)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    fundamental = relationship("Fundamental", back_populates="candidate", uselist=False, cascade="all, delete-orphan")
    price_data = relationship("PriceData", back_populates="candidate")
    news_articles = relationship("NewsArticle", back_populates="candidate")
    predictions = relationship("Prediction", back_populates="candidate")


class Fundamental(Base):
    __tablename__ = "fundamental"

    id = Column(String, primary_key=True, default=_uuid)
    candidate_id = Column(String, ForeignKey("ipo_candidate.id"), unique=True, index=True)

    pe_ratio = Column(Numeric(10, 2), nullable=True)
    pb_ratio = Column(Numeric(10, 2), nullable=True)
    roe = Column(Numeric(8, 4), nullable=True)
    debt_to_equity = Column(Numeric(10, 4), nullable=True)
    total_assets_idr = Column(BigInteger, nullable=True)
    revenue_idr = Column(BigInteger, nullable=True)
    net_income_idr = Column(BigInteger, nullable=True)
    revenue_growth_yoy = Column(Numeric(8, 4), nullable=True)
    sector_avg_pe = Column(Numeric(10, 2), nullable=True)
    sector_avg_pb = Column(Numeric(10, 2), nullable=True)
    report_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    candidate = relationship("IpoCandidate", back_populates="fundamental")


class PriceData(Base):
    __tablename__ = "price_data"

    id = Column(String, primary_key=True, default=_uuid)
    candidate_id = Column(String, ForeignKey("ipo_candidate.id"), index=True)
    date = Column(Date, nullable=False)
    open = Column(Numeric(12, 2), nullable=True)
    high = Column(Numeric(12, 2), nullable=True)
    low = Column(Numeric(12, 2), nullable=True)
    close = Column(Numeric(12, 2), nullable=True)
    volume = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    candidate = relationship("IpoCandidate", back_populates="price_data")


class NewsArticle(Base):
    __tablename__ = "news_article"

    id = Column(String, primary_key=True, default=_uuid)
    candidate_id = Column(String, ForeignKey("ipo_candidate.id"), index=True)
    headline = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    source = Column(String, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    sentiment_score = Column(Numeric(5, 3), nullable=True)
    sentiment_label = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    candidate = relationship("IpoCandidate", back_populates="news_articles")


class Prediction(Base):
    __tablename__ = "prediction"

    id = Column(String, primary_key=True, default=_uuid)
    candidate_id = Column(String, ForeignKey("ipo_candidate.id"), index=True)

    model_version = Column(String, nullable=False)
    layer1_probability = Column(Numeric(6, 4), nullable=True)
    layer1_label = Column(String, nullable=True)
    layer1_feature_importance = Column(JSON, nullable=True)

    layer2_probability = Column(Numeric(6, 4), nullable=True)
    layer2_label = Column(String, nullable=True)
    layer2_feature_importance = Column(JSON, nullable=True)

    sentiment_score = Column(Numeric(5, 3), nullable=True)
    sentiment_magnitude = Column(Numeric(5, 3), nullable=True)
    news_count = Column(Integer, default=0)

    composite_score = Column(Numeric(6, 4), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    candidate = relationship("IpoCandidate", back_populates="predictions")


class AnalysisRun(Base):
    __tablename__ = "analysis_run"

    id = Column(String, primary_key=True, default=_uuid)
    status = Column(String, index=True, default=RunStatus.QUEUED)
    top_n = Column(Integer, default=5)
    trigger_type = Column(String, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), index=True, default=lambda: datetime.now(timezone.utc))

    candidates = relationship("AnalysisCandidate", back_populates="run", cascade="all, delete-orphan")
    result = relationship("AnalysisResult", back_populates="run", uselist=False, cascade="all, delete-orphan")


class AnalysisCandidate(Base):
    __tablename__ = "analysis_candidate"

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("analysis_run.id"), index=True)
    candidate_id = Column(String, ForeignKey("ipo_candidate.id"))
    prediction_id = Column(String, ForeignKey("prediction.id"))
    composite_rank = Column(Integer, nullable=False)

    run = relationship("AnalysisRun", back_populates="candidates")


class AnalysisResult(Base):
    __tablename__ = "analysis_result"

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("analysis_run.id"), unique=True, index=True)
    candidate_count = Column(Integer, nullable=False)
    prompt = Column(Text, nullable=False)
    top_candidates_summary = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    run = relationship("AnalysisRun", back_populates="result")
