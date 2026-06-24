import logging
from database.repository import repository
from database.models import TradeRecord

logger = logging.getLogger(__name__)

class WinRateCalculator:
    @staticmethod
    def calculate():
        with repository.get_session() as session:
            trades = session.query(TradeRecord).filter(TradeRecord.status == 'CLOSED').all()
            if not trades:
                return 0.0
                
            wins = sum(1 for t in trades if t.pnl > 0)
            return round((wins / len(trades)) * 100, 2)
