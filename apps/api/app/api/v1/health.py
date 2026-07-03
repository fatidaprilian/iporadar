"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def health_check() -> dict:
    """Return service health status."""
    from app.ml.models import get_layer1_model, get_layer2_model

    l1 = get_layer1_model()
    l2 = get_layer2_model()
    return {
        "status": "healthy",
        "modelsLoaded": l1.model is not None and l2.model is not None,
    }
