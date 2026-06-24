import logging
from database.repository import repository
from database.models import TradeRecord

logger = logging.getLogger(__name__)

class TradeStats:
    @staticmethod
    def get_summary():
        with repository.get_session() as session:
            trades = session.query(TradeRecord).filter(TradeRecord.status == 'CLOSED').all()
            if not trades:
                return {"total_trades": 0, "pnl": 0.0, "profit_factor": 0.0}
                
            gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
            gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
            
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            total_pnl = sum(t.pnl for t in trades)
            
            return {
                "total_trades": len(trades),
                "pnl": round(total_pnl, 2),
                "profit_factor": round(profit_factor, 2)
            }
