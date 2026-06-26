"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.predict import router as predict_router
from app.api.v1.sentiment import router as sentiment_router

router = APIRouter()

router.include_router(health_router, tags=["health"])
router.include_router(predict_router, tags=["prediction"])
router.include_router(sentiment_router, tags=["sentiment"])
