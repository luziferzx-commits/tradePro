import pandas as pd
from datetime import datetime, timedelta
from database.repository import repository
from database.models import ShadowTrade, TradeSignal
import os

class ShadowReportGenerator:
    def __init__(self):
        os.makedirs("reports", exist_ok=True)
        
    def generate_daily_report(self):
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=1)
        
        with repository.get_session() as session:
            # 1. Fetch Shadow Trades
            trades = session.query(ShadowTrade).filter(
                ShadowTrade.open_time >= start_time
            ).all()
            
            # 2. Fetch ML Rejections
            rejections = session.query(TradeSignal).filter(
                TradeSignal.timestamp >= start_time,
                TradeSignal.ml_rejected == True
            ).all()
            
            # 3. Fetch Gemini Rejections
            gemini_rejections = session.query(TradeSignal).filter(
                TradeSignal.timestamp >= start_time,
                TradeSignal.ml_rejected == False,
                TradeSignal.ai_approved == False
            ).all()
            
        trade_count = len(trades)
        total_pnl = sum([t.pnl for t in trades if t.pnl is not None])
        wins = sum([1 for t in trades if t.pnl is not None and t.pnl > 0])
        losses = sum([1 for t in trades if t.pnl is not None and t.pnl <= 0])
        
        win_sum = sum([t.pnl for t in trades if t.pnl is not None and t.pnl > 0])
        loss_sum = abs(sum([t.pnl for t in trades if t.pnl is not None and t.pnl <= 0]))
        
        virtual_pf = win_sum / loss_sum if loss_sum > 0 else (99.9 if win_sum > 0 else 0.0)
        
        report_str = f"# Daily Shadow Trading Report ({end_time.strftime('%Y-%m-%d')})\n\n"
        report_str += f"## 📊 Execution Summary\n"
        report_str += f"- **Shadow Trades Executed:** {trade_count}\n"
        report_str += f"- **Virtual PnL:** {total_pnl:.2f}\n"
        report_str += f"- **Virtual PF:** {virtual_pf:.3f}\n"
        report_str += f"- **Win/Loss:** {wins} / {losses}\n\n"
        
        report_str += f"## 🤖 Pipeline Filters\n"
        report_str += f"- **Rejected by ML Predictor:** {len(rejections)}\n"
        report_str += f"- **Rejected by Gemini Review:** {len(gemini_rejections)}\n\n"
        
        if len(rejections) > 0:
            report_str += f"### Top ML Rejection Reasons\n"
            reasons = {}
            for r in rejections:
                reasons[r.ml_rejection_reason] = reasons.get(r.ml_rejection_reason, 0) + 1
            for reason, count in reasons.items():
                report_str += f"- {reason}: {count} times\n"
                
        report_path = f"reports/shadow_report_{end_time.strftime('%Y%m%d')}.md"
        with open(report_path, "w", encoding='utf-8') as f:
            f.write(report_str)
            
        print(f"Shadow report generated: {report_path}")

shadow_report = ShadowReportGenerator()

if __name__ == "__main__":
    shadow_report.generate_daily_report()
