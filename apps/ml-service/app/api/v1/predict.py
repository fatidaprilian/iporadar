"""Prediction endpoint - placeholder for Phase 2."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/predict")
async def predict() -> dict:
    """Run ML inference on IPO candidates. Implemented in Phase 2."""
    return {"message": "Prediction endpoint - not yet implemented"}
