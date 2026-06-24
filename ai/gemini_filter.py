import logging
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError
from config.settings import settings
from ai.memory_builder import MemoryBuilder

logger = logging.getLogger(__name__)

class AIReviewResponse(BaseModel):
    approve: bool
    confidence: int
    reason: str

class GeminiFilter:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def evaluate_signal(self, symbol: str, market_score: dict, regime: dict, indicators: dict) -> dict:
        """
        Queries Gemini to review the trade signal using Structured Outputs.
        Returns: {"approve": bool, "confidence": int, "reason": str}
        """
        if not self.client:
            logger.warning("Gemini API key not set. Defaulting to approve=False.")
            return {"approve": False, "confidence": 0, "reason": "API Key Missing"}

        memory_context = MemoryBuilder.build_context()

        direction = market_score.get('final_direction', 'UNKNOWN')
        score_val = market_score.get('final_score', 0)

        prompt = f"""
        You are the Chief Risk Officer (CRO) AI for a sophisticated quantitative trading firm.
        Evaluate this proposed {direction} trade for {symbol}. 
        The quantitative scoring engine gave it a final decision score of {score_val} / 100.
        
        Score Breakdown:
        - Trend Score: {market_score.get('trend_score')} (Positive = Buy Bias, Negative = Sell Bias)
        - Breakout Score: {market_score.get('breakout_score')}
        - Pullback Score: {market_score.get('pullback_score')}
        - Reversal Score: {market_score.get('reversal_score')}
        - Session Score (Liquidity): {market_score.get('session_score')}
        
        Market Regime: {regime}
        Indicators: {indicators}
        Historical Context: {memory_context}
        
        Review the breakdown. Is it safe to enter a {direction} trade here? Evaluate structural weaknesses.
        """

        try:
            logger.info("Sending request to Gemini API...")
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AIReviewResponse,
                )
            )
            
            logger.info("Received response from Gemini API.")
            
            # response.text is guaranteed to be a JSON string matching the schema
            decision_dict = json.loads(response.text)
            validated_decision = AIReviewResponse(**decision_dict)
            
            if not validated_decision.approve:
                logger.info(f"AI rejected trade: {validated_decision.reason}")
                return {"approve": False, "confidence": validated_decision.confidence, "reason": validated_decision.reason}
                
            if validated_decision.confidence < settings.MIN_AI_CONFIDENCE:
                logger.info(f"AI confidence too low ({validated_decision.confidence} < {settings.MIN_AI_CONFIDENCE}). Reason: {validated_decision.reason}")
                return {"approve": False, "confidence": validated_decision.confidence, "reason": validated_decision.reason}
                
            return {
                "approve": True,
                "confidence": validated_decision.confidence,
                "reason": validated_decision.reason
            }
            
        except ValidationError as e:
            logger.error(f"Gemini evaluation Pydantic validation failed: {e}")
            return {"approve": False, "confidence": 0, "reason": "Invalid structured output"}
        except Exception as e:
            logger.error(f"Gemini API error / timeout: {e}")
            return {"approve": False, "confidence": 0, "reason": "API error / timeout / invalid structured output"}
