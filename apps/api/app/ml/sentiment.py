import logging
import os
from typing import List

# Setup logging
logger = logging.getLogger(__name__)

# To speed up cold starts in local dev if no GPU, set torch to use CPU
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

class SentimentAnalyzer:
    def __init__(self):
        self.model_name = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
        self._pipeline = None
        
    def _get_pipeline(self):
        if self._pipeline is None:
            logger.info(f"Loading XLM-RoBERTa sentiment model: {self.model_name}")
            try:
                from transformers import pipeline
                self._pipeline = pipeline("sentiment-analysis", model=self.model_name, tokenizer=self.model_name)
                logger.info("Model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                raise e
        return self._pipeline

    def analyze(self, texts: List[str]) -> List[dict]:
        """
        Analyze sentiment for a list of texts.
        Returns a list of dicts with score (-1.0 to 1.0) and magnitude.
        cardiffnlp outputs: LABEL_0 (negative), LABEL_1 (neutral), LABEL_2 (positive)
        """
        if not texts:
            return []
            
        pipe = self._get_pipeline()
        
        # Truncate texts to avoid token limit errors
        # XLM-RoBERTa handles 512 tokens max. We truncate raw string approx.
        truncated_texts = [text[:1500] for text in texts]
        
        results = []
        try:
            predictions = pipe(truncated_texts)
            
            for text, pred in zip(texts, predictions):
                label = pred['label']
                score = pred['score']  # Confidence (magnitude)
                
                # Map to our -1.0 to 1.0 scale
                if label == 'LABEL_0' or label == 'negative':
                    mapped_score = -1.0 * score
                    final_label = 'negative'
                elif label == 'LABEL_2' or label == 'positive':
                    mapped_score = 1.0 * score
                    final_label = 'positive'
                else:
                    # Neutral
                    mapped_score = 0.0
                    final_label = 'neutral'
                    
                results.append({
                    "text": text,
                    "sentiment_score": mapped_score,
                    "magnitude": score,
                    "label": final_label
                })
        except Exception as e:
            logger.error(f"Inference error: {e}")
            # Fallback for errors to prevent crashing the whole pipeline
            results = [{
                "text": text,
                "sentiment_score": 0.0,
                "magnitude": 0.0,
                "label": "neutral"
            } for text in texts]
            
        return results

# Singleton instance
analyzer = SentimentAnalyzer()

def get_sentiment_analyzer():
    return analyzer
