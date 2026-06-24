import logging
from database.models import MarketState, TradeSignal, TradeRecord
from database.repository import repository

logger = logging.getLogger(__name__)

class DatabaseLogger:
    @staticmethod
    def log_market_state(symbol, timeframe, close_price, indicators, regime) -> MarketState:
        state = MarketState(
            symbol=symbol,
            timeframe=timeframe,
            close_price=close_price,
            rsi=indicators.get('rsi'),
            macd=indicators.get('macd'),
            macd_signal=indicators.get('macd_signal'),
            macd_hist=indicators.get('macd_hist'),
            ema50=indicators.get('ema50'),
            ema200=indicators.get('ema200'),
            atr=indicators.get('atr'),
            regime=regime.get('trend_state'),
            volatility_state=regime.get('volatility_state')
        )
        return repository.save(state)

    @staticmethod
    def log_signal(market_state_id, strategy_name, direction, market_score=None) -> TradeSignal:
        signal = TradeSignal(
            market_state_id=market_state_id,
            strategy_name=strategy_name,
            direction=direction,
            trend_score=market_score.get('trend_score') if market_score else None,
            breakout_score=market_score.get('breakout_score') if market_score else None,
            pullback_score=market_score.get('pullback_score') if market_score else None,
            reversal_score=market_score.get('reversal_score') if market_score else None,
            session_score=market_score.get('session_score') if market_score else None,
            total_buy_score=market_score.get('total_buy_score') if market_score else None,
            total_sell_score=market_score.get('total_sell_score') if market_score else None,
            final_score=market_score.get('final_score') if market_score else None
        )
        return repository.save(signal)

    @staticmethod
    def update_ai_review(signal_id, approved, confidence, reason, model):
        with repository.get_session() as session:
            signal = session.query(TradeSignal).filter(TradeSignal.id == signal_id).first()
            if signal:
                signal.ai_approved = approved
                signal.ai_confidence = confidence
                signal.ai_reason = reason
                signal.ai_model = model
                session.commit()

    @staticmethod
    def log_trade_execution(signal_id, ticket, symbol, direction, volume, open_price, sl, tp, open_time):
        trade = TradeRecord(
            signal_id=signal_id,
            ticket=ticket,
            symbol=symbol,
            direction=direction,
            volume=volume,
            open_price=open_price,
            sl=sl,
            tp=tp,
            open_time=open_time,
            status='OPEN'
        )
        return repository.save(trade)
    
    @staticmethod
    def log_trade_close(ticket, close_price, close_time, pnl):
        with repository.get_session() as session:
            trade = session.query(TradeRecord).filter(TradeRecord.ticket == ticket).first()
            if trade:
                trade.close_price = close_price
                trade.close_time = close_time
                trade.pnl = pnl
                trade.status = 'CLOSED'
                session.commit()
