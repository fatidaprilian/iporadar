"""Sentiment analysis endpoint - placeholder for Phase 2."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/sentiment")
async def analyze_sentiment() -> dict:
    """Extract sentiment from headlines. Implemented in Phase 2."""
    return {"message": "Sentiment endpoint - not yet implemented"}
