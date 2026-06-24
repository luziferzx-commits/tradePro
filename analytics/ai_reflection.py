import os
from datetime import datetime, timedelta
from database.repository import repository
from database.models import ShadowTrade, TradeSignal, MarketState
from ai.gemini_filter import GeminiFilter
import logging

logger = logging.getLogger("GoldBot.AIReflection")

class AIReflection:
    def __init__(self):
        self.ai = GeminiFilter()
        
    def generate_daily_reflection(self):
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=1)
        
        with repository.get_session() as session:
            trades = session.query(ShadowTrade).join(TradeSignal).filter(
                ShadowTrade.open_time >= start_time
            ).all()
            
            if not trades:
                logger.info("No trades to reflect upon today.")
                return
                
            trade_summaries = []
            for t in trades:
                sig = t.signal
                res = "WIN" if (t.pnl and t.pnl > 0) else ("LOSS" if (t.pnl and t.pnl <= 0) else "OPEN")
                summary = (
                    f"Trade ID: {t.id} | Dir: {t.direction} | Vol: {t.volume} | Result: {res}\n"
                    f"ML Prob: {sig.ml_probability:.2f} | Setup Score: {sig.final_score:.2f} | Reason: {sig.ml_rejection_reason}\n"
                )
                trade_summaries.append(summary)
                
        prompt = f"""
        You are a Senior Quantitative Analyst at a hedge fund.
        Please review the following trades executed by our quantitative system over the last 24 hours.
        
        Trades:
        {''.join(trade_summaries)}
        
        Provide a post-mortem analysis (AI Reflection Report):
        1. Summarize the overall performance.
        2. Identify any patterns in the losing trades (e.g., was ML probability too close to the threshold? Was the setup score actually weak?).
        3. Provide 1-2 actionable research recommendations for improving the ML or Quant models.
        
        Format your response in Markdown.
        """
        
        logger.info(f"Sending {len(trades)} trades to Gemini for Reflection...")
        response = self.ai.model.generate_content(prompt)
        
        date_str = end_time.strftime("%Y%m%d")
        report_path = f"reports/ai_reflection_{date_str}.md"
        
        os.makedirs("reports", exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# AI Daily Reflection ({date_str})\n\n")
            f.write(response.text)
            
        logger.info(f"AI Reflection Report generated: {report_path}")

if __name__ == "__main__":
    reflection = AIReflection()
    reflection.generate_daily_reflection()
