"""IPO Radar ML Service - FastAPI Application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as v1_router
from app.config import settings

app = FastAPI(
    title="IPO Radar ML Service",
    description="ML inference and sentiment analysis for BEI IPO prediction",
    version="0.1.0",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else [],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")
