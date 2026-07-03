"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.predict import router as predict_router
from app.api.v1.sentiment import router as sentiment_router
from app.api.v1.candidates import router as candidates_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.scraper import router as scraper_router

router = APIRouter()

router.include_router(health_router, prefix="/health", tags=["health"])
router.include_router(predict_router, prefix="/predict", tags=["prediction"])
router.include_router(sentiment_router, prefix="/sentiment", tags=["sentiment"])
router.include_router(candidates_router, prefix="/candidates", tags=["candidates"])
router.include_router(analysis_router, prefix="/analysis", tags=["analysis"])
router.include_router(scraper_router, prefix="/scraper", tags=["scraper"])
