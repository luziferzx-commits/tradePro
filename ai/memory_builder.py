import logging
from database.repository import repository
from database.models import TradeRecord

logger = logging.getLogger(__name__)

class MemoryBuilder:
    @staticmethod
    def build_context() -> dict:
        """
        Retrieves the last 20 and 100 trade performance, and current drawdown.
        """
        try:
            with repository.get_session() as session:
                trades = session.query(TradeRecord).filter(TradeRecord.status == 'CLOSED').order_by(TradeRecord.close_time.desc()).limit(100).all()
                
                if not trades:
                    return {
                        "last_20_winrate": 0,
                        "last_100_winrate": 0,
                        "current_drawdown": 0
                    }
                    
                # Calculate last 20
                last_20 = trades[:20]
                wins_20 = sum(1 for t in last_20 if t.pnl and t.pnl > 0)
                wr_20 = (wins_20 / len(last_20)) * 100 if last_20 else 0
                
                # Calculate last 100
                wins_100 = sum(1 for t in trades if t.pnl and t.pnl > 0)
                wr_100 = (wins_100 / len(trades)) * 100 if trades else 0
                
                # Drawdown approximation (simple PnL sum for now)
                cumulative_pnl = 0
                peak = 0
                max_dd = 0
                for t in reversed(trades): # Oldest first
                    if t.pnl:
                        cumulative_pnl += t.pnl
                        if cumulative_pnl > peak:
                            peak = cumulative_pnl
                        dd = peak - cumulative_pnl
                        if dd > max_dd:
                            max_dd = dd
                            
                return {
                    "last_20_winrate": round(wr_20, 2),
                    "last_100_winrate": round(wr_100, 2),
                    "current_drawdown_usd": round(max_dd, 2)
                }
        except Exception as e:
            logger.error(f"Error building memory context: {e}")
            return {}
