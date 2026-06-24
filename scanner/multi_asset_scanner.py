"""scanner/multi_asset_scanner.py"""
import logging
from typing import Optional
from datetime import datetime
import pandas as pd
import numpy as np

from market.symbol_registry import SymbolRegistry
from market.market_metadata import MarketMetadata
from scanner.opportunity_ranker import OpportunityRanker

logger = logging.getLogger(__name__)

class MultiAssetScanner:
    def __init__(self, registry: SymbolRegistry, metadata: MarketMetadata, mt5_client=None, predictor=None):
        self.registry = registry
        self.metadata = metadata
        self.mt5_client = mt5_client
        self.predictor = predictor

    def scan_all(self) -> tuple[list[dict], list[dict]]:
        """
        Scans all enabled symbols.
        Returns (approved_opportunities, rejected_opportunities)
        """
        symbols = self.registry.get_enabled_symbols()
        signals = []
        
        logger.info(f"Starting multi-asset scan for {len(symbols)} symbols...")
        
        for meta in symbols:
            symbol = meta["symbol"]
            try:
                sig = self._scan_single_symbol(symbol, meta)
                if sig:
                    signals.append(sig)
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                signals.append({
                    'timestamp': datetime.now().isoformat(),
                    'symbol': symbol,
                    'side': 'UNKNOWN',
                    'model_probability': 0.0,
                    'market_score': 0,
                    'expected_r': 0.0,
                    'spread_points': 9999,
                    'volatility_regime': 'ERROR',
                    'status': 'REJECTED',
                    'reason': f"Scan Exception: {str(e)}",
                    'final_score': 0.0
                })
                
        # Rank and filter signals that are not already rejected
        to_rank = [s for s in signals if s.get('status') != 'REJECTED']
        already_rejected = [s for s in signals if s.get('status') == 'REJECTED']
        
        approved, newly_rejected = OpportunityRanker.rank_and_filter(to_rank, self.metadata)
        
        rejected = newly_rejected + already_rejected
        return approved, rejected

    def _scan_single_symbol(self, symbol: str, meta: dict) -> Optional[dict]:
        """Generates a raw signal for a single symbol using real data and ML models."""
        from config.settings import settings
        import MetaTrader5 as mt5
        
        if not self.mt5_client or not self.predictor:
            logger.warning(f"Scanner missing mt5_client or predictor. Returning None for {symbol}.")
            return None
            
        resolved_symbol = self.mt5_client.resolve_symbol(symbol)
        
        # 1. Fetch data
        df = self.mt5_client.get_historical_data(symbol, settings.TIMEFRAME, 500)
        if df is None or len(df) < 200:
            return None # Reject missing data
            
        # 2. Add indicators
        from strategy.indicators import IndicatorCalculator
        from market.regime_detector import RegimeDetector
        from strategy.market_score import MarketScoreCalculator
        from strategy.scorer import MultiScorer
        
        df = IndicatorCalculator.add_indicators(df)
        indicators = IndicatorCalculator.get_latest_indicators(df)
        regime = RegimeDetector.detect(df)
        
        # 3. H4 Trend
        df_h4 = self.mt5_client.get_h4_data(symbol, 50)
        h4_trend = "NEUTRAL"
        if df_h4 is not None and len(df_h4) >= 50:
            h4_ema50 = df_h4['close'].ewm(span=50).mean().iloc[-1]
            h4_close = df_h4['close'].iloc[-1]
            h4_trend = "UP" if h4_close > h4_ema50 else "DOWN"
            
        # 4. Market Score
        market_type = meta.get("asset_class", meta.get("market_type", "FOREX")).upper()
        market_score = MarketScoreCalculator.calculate(df, regime, h4_trend=h4_trend, asset_class=market_type)
        final_dir = market_score['final_direction']
        
        if final_dir == "NEUTRAL":
            return {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'side': 'NEUTRAL',
                'model_probability': 0.0,
                'market_score': 0,
                'expected_r': 0.0,
                'spread_points': 9999,
                'volatility_regime': 'NORMAL',
                'status': 'REJECTED',
                'reason': 'Quant neutral'
            }
            
        # 5. ML Features
        recent_high = df.iloc[-3]['recent_high_20'] if len(df) > 2 else df['high'].iloc[-1]
        recent_low = df.iloc[-3]['recent_low_20'] if len(df) > 2 else df['low'].iloc[-1]
        
        atr = indicators.get('atr', 1e-5)
        if atr <= 0: atr = 1e-5
        
        rh_dist = (recent_high - df['close'].iloc[-1]) / atr
        rl_dist = (df['close'].iloc[-1] - recent_low) / atr
        
        current_time = df['time'].iloc[-1]
        market_type = meta.get("asset_class", meta.get("market_type", "FOREX")).upper()
        
        ml_features = {
            "final_score": market_score['final_score'],
            "trend_score": MultiScorer.get_trend_score(df, regime),
            "breakout_score": MultiScorer.get_breakout_score(df),
            "reversal_score": MultiScorer.get_reversal_score(df),
            "session_score": MultiScorer.get_session_score(current_time, market_type),
            "atr": atr,
            "atr_pct": (atr / df['close'].iloc[-1] * 100) if df['close'].iloc[-1] > 0 else 0,
            "adx": indicators.get('adx', 0),
            "ema50_slope": indicators.get('ema50_slope', 0),
            "rsi": indicators.get('rsi', 50),
            "macd": indicators.get('macd', 0),
            "hour_utc": current_time.hour,
            "is_high_volatility": 1 if regime.get('volatility_state') == "HIGH_VOLATILITY" else 0,
            "is_buy": 1 if final_dir == "BUY" else 0,
            "recent_high_20_distance": rh_dist,
            "recent_low_20_distance": rl_dist,
            "recent_high_20_distance_pct": (recent_high - df['close'].iloc[-1]) / df['close'].iloc[-1] * 100 if df['close'].iloc[-1] > 0 else 0,
            "recent_low_20_distance_pct": (df['close'].iloc[-1] - recent_low) / df['close'].iloc[-1] * 100 if df['close'].iloc[-1] > 0 else 0
        }
        
        # 6. Market Memory AI & Predict
        from memory.market_memory_v2 import market_memory_v2
        
        # Determine Session
        hour = current_time.hour
        if hour >= 13 and hour < 21: session = "NY"
        elif hour >= 7 and hour < 13: session = "London"
        else: session = "Asia"
            
        vol_state = regime.get("volatility_state", "NORMAL_VOLATILITY")
        atr_bucket = "HIGH" if vol_state == "HIGH_VOLATILITY" else "LOW" if vol_state == "LOW_VOLATILITY" else "NORMAL"
        
        memory_data = market_memory_v2.get_memory(session, regime.get("trend_state", "UNKNOWN"), atr_bucket, final_dir)
        
        # In Single Asset mode, predict took 1 argument. 
        ml_result = self.predictor.predict(ml_features)
        
        # Memory AI Boosting Logic
        conf = memory_data.get("memory_confidence", "LOW")
        win_rate = memory_data.get("memory_win_rate", 0.0)
        original_prob = ml_result.get("probability", 0.0)
        
        if conf == "HIGH":
            if win_rate > 0.55:
                ml_result["probability"] = min(1.0, original_prob + 0.10)
                ml_result["approved"] = (ml_result["probability"] >= self.predictor.threshold)
                ml_result["reason"] = "approved_by_memory_boost" if ml_result["approved"] else ml_result["reason"]
            elif win_rate < 0.45:
                ml_result["probability"] = max(0.0, original_prob - 0.10)
                ml_result["approved"] = (ml_result["probability"] >= self.predictor.threshold)
                ml_result["reason"] = "rejected_by_memory_penalty" if not ml_result["approved"] else ml_result["reason"]

        
        # 7. Spread
        sym_info = mt5.symbol_info(resolved_symbol)
        spread = sym_info.spread if sym_info else 999
        
        return {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'side': final_dir,
            'model_probability': ml_result.get("candidate_probability", 0.0),
            'market_score': market_score['final_score'],
            'expected_r': ml_result.get("expected_rr", 0.0),
            'spread_points': spread,
            'volatility_regime': regime.get('volatility_state', 'NORMAL')
        }
