from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.ml.sentiment import get_sentiment_analyzer

router = APIRouter()

class SentimentRequest(BaseModel):
    texts: List[str]

class SentimentResult(BaseModel):
    text: str
    sentiment_score: float
    magnitude: float
    label: str

class SentimentResponse(BaseModel):
    results: List[SentimentResult]

@router.post("/", response_model=SentimentResponse)
def analyze_sentiment(request: SentimentRequest):
    """
    Analyzes sentiment of text inputs using XLM-RoBERTa.
    """
    analyzer = get_sentiment_analyzer()
    results_raw = analyzer.analyze(request.texts)
    
    results = [
        SentimentResult(
            text=r["text"],
            sentiment_score=r["sentiment_score"],
            magnitude=r["magnitude"],
            label=r["label"]
        ) for r in results_raw
    ]
        
    return SentimentResponse(results=results)
