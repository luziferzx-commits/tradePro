from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class MarketState(Base):
    __tablename__ = 'market_states'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    symbol = Column(String(20), index=True)
    timeframe = Column(String(10))
    close_price = Column(Float)
    
    # Technical Indicators
    rsi = Column(Float)
    macd = Column(Float)
    macd_signal = Column(Float)
    macd_hist = Column(Float)
    ema50 = Column(Float)
    ema200 = Column(Float)
    atr = Column(Float)
    
    # Regime
    regime = Column(String(50))
    volatility_state = Column(String(50))
    
    # Related signal (if any)
    signal = relationship("TradeSignal", back_populates="market_state", uselist=False)

class TradeSignal(Base):
    __tablename__ = 'trade_signals'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    market_state_id = Column(Integer, ForeignKey('market_states.id'))
    
    strategy_name = Column(String(100))
    direction = Column(String(10)) # BUY, SELL
    
    # V2 Score Components
    trend_score = Column(Float, nullable=True)
    breakout_score = Column(Float, nullable=True)
    pullback_score = Column(Float, nullable=True)
    reversal_score = Column(Float, nullable=True)
    session_score = Column(Float, nullable=True)
    total_buy_score = Column(Float, nullable=True)
    total_sell_score = Column(Float, nullable=True)
    final_score = Column(Float, nullable=True)
    
    # V4 ML Prediction
    ml_probability = Column(Float, nullable=True)
    ml_model_version = Column(String(50), nullable=True)
    ml_feature_hash = Column(String(64), nullable=True)
    ml_expected_rr = Column(Float, nullable=True)
    ml_expected_holding_time = Column(Float, nullable=True)
    ml_expected_drawdown = Column(Float, nullable=True)
    ml_rejected = Column(Boolean, default=False)
    ml_rejection_reason = Column(String(200), nullable=True)
    
    # AI Review
    ai_approved = Column(Boolean, nullable=True)
    ai_confidence = Column(Integer, nullable=True)
    ai_reason = Column(String(1000), nullable=True)
    ai_model = Column(String(100), nullable=True)
    
    market_state = relationship("MarketState", back_populates="signal")
    trade = relationship("TradeRecord", back_populates="signal", uselist=False)
    shadow_trade = relationship("ShadowTrade", back_populates="signal", uselist=False)

class ShadowTrade(Base):
    __tablename__ = 'shadow_trades'
    
    id = Column(Integer, primary_key=True)
    signal_id = Column(Integer, ForeignKey('trade_signals.id'))
    
    symbol = Column(String(20))
    direction = Column(String(10))
    volume = Column(Float)
    
    open_time = Column(DateTime)
    open_price = Column(Float) # Real MT5 tick ask/bid
    sl = Column(Float)
    tp = Column(Float)
    
    close_time = Column(DateTime, nullable=True)
    close_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    
    status = Column(String(20)) # OPEN, CLOSED
    
    signal = relationship("TradeSignal", back_populates="shadow_trade")

class TradeRecord(Base):
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    signal_id = Column(Integer, ForeignKey('trade_signals.id'))
    
    ticket = Column(Integer, unique=True, index=True)
    symbol = Column(String(20))
    direction = Column(String(10))
    volume = Column(Float)
    
    open_time = Column(DateTime)
    open_price = Column(Float)
    sl = Column(Float)
    tp = Column(Float)
    
    close_time = Column(DateTime, nullable=True)
    close_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    
    status = Column(String(20)) # OPEN, CLOSED
    
    signal = relationship("TradeSignal", back_populates="trade")
