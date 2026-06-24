import json
import os
from datetime import datetime, timedelta
from database.repository import repository
from database.models import ShadowTrade, TradeSignal
import logging

logger = logging.getLogger("GoldBot.ModelHealth")

class ModelHealthMonitor:
    def __init__(self):
        self.health_file = "models/production/health_score.json"
        
    def calculate_health(self):
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=1)
        
        base_score = 100
        
        with repository.get_session() as session:
            # Rejections
            all_signals = session.query(TradeSignal).filter(
                TradeSignal.timestamp >= start_time
            ).all()
            
            total_setups = len(all_signals)
            drift_rejections = sum([1 for s in all_signals if s.ml_rejected and "HIGH DRIFT" in str(s.ml_rejection_reason)])
            ml_rejections = sum([1 for s in all_signals if s.ml_rejected])
            gemini_rejections = sum([1 for s in all_signals if not s.ml_rejected and s.ai_approved == False])
            
            # Trades
            trades = session.query(ShadowTrade).filter(
                ShadowTrade.open_time >= start_time
            ).all()
            
            wins = sum([1 for t in trades if t.pnl is not None and t.pnl > 0])
            losses = sum([1 for t in trades if t.pnl is not None and t.pnl <= 0])
            win_sum = sum([t.pnl for t in trades if t.pnl is not None and t.pnl > 0])
            loss_sum = abs(sum([t.pnl for t in trades if t.pnl is not None and t.pnl <= 0]))
            
            virtual_pf = win_sum / loss_sum if loss_sum > 0 else (99.9 if win_sum > 0 else 0.0)
            
        # Penalties
        if drift_rejections > 0:
            base_score -= 10
            
        if len(trades) > 0 and virtual_pf < 1.0:
            base_score -= 20
            
        if total_setups > 0:
            gemini_reject_pct = gemini_rejections / total_setups
            if gemini_reject_pct > 0.5:
                base_score -= 10
                
        # Save health
        health_data = {
            "timestamp": end_time.isoformat(),
            "health_score": base_score,
            "metrics": {
                "drift_rejections": drift_rejections,
                "virtual_pf": virtual_pf,
                "gemini_rejections": gemini_rejections,
                "total_shadow_trades": len(trades)
            }
        }
        
        os.makedirs(os.path.dirname(self.health_file), exist_ok=True)
        with open(self.health_file, "w") as f:
            json.dump(health_data, f, indent=4)
            
        logger.info(f"Model Health Score updated: {base_score}/100")
        return base_score
        
    def get_latest_health(self):
        if not os.path.exists(self.health_file):
            return 100
            
        try:
            with open(self.health_file, "r") as f:
                data = json.load(f)
            return data.get("health_score", 100)
        except Exception:
            return 100

health_monitor = ModelHealthMonitor()

if __name__ == "__main__":
    health_monitor.calculate_health()
