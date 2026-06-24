import pandas as pd
from datetime import datetime
from market.regime_detector import RegimeDetector
from strategy.market_score import MarketScoreCalculator

class BacktestRunner:
    def __init__(self, spread_points: float = 20.0):
        self.spread_points = spread_points
        # Assume 3 decimals for XAUUSD for calculation if MT5 is not actively used for tick info
        self.point = 0.001

    def run(self, records: list, scores_list: list, threshold: float, atr_multiplier: float, rr_ratio: float, target_setup: str,
            filter_regime: str = "ALL", filter_session: str = "ALL", cooldown_candles: int = 0, filter_atr: str = "ALL", filter_direction: str = "BOTH",
            atr_percentiles: dict = None) -> list:
        """
        Runs the backtest over the pre-calculated list of dicts (records) for a specific target_setup.
        """
        trades = []
        in_trade = False
        current_trade = None
        
        consecutive_losses = 0
        cooldown_until = 0
        
        # Start at 200 to allow indicators to warm up
        for i in range(200, len(records)):
            candle = records[i]
            
            if in_trade:
                # Check for SL/TP hits using current candle
                high = candle['high']
                low = candle['low']
                spread_val = self.spread_points * self.point
                
                hit_sl = False
                hit_tp = False
                exit_price = 0.0
                
                if current_trade['direction'] == "BUY":
                    if low <= current_trade['sl']:
                        hit_sl = True
                        exit_price = current_trade['sl']
                    if high >= current_trade['tp']:
                        hit_tp = True
                        exit_price = current_trade['tp']
                else: # SELL
                    ask_high = high + spread_val
                    ask_low = low + spread_val
                    
                    if ask_high >= current_trade['sl']:
                        hit_sl = True
                        exit_price = current_trade['sl']
                    if ask_low <= current_trade['tp']:
                        hit_tp = True
                        exit_price = current_trade['tp']
                
                if hit_sl and hit_tp:
                    hit_tp = False 
                    exit_price = current_trade['sl']
                    
                if hit_sl:
                    current_trade['result_r'] = -1.0
                    current_trade['exit_price'] = exit_price
                    current_trade['close_time'] = candle['time']
                    trades.append(current_trade)
                    in_trade = False
                    current_trade = None
                    
                    consecutive_losses += 1
                    if consecutive_losses >= 2 and cooldown_candles > 0:
                        cooldown_until = i + cooldown_candles
                        consecutive_losses = 0
                        
                elif hit_tp:
                    current_trade['result_r'] = rr_ratio
                    current_trade['exit_price'] = exit_price
                    current_trade['close_time'] = candle['time']
                    trades.append(current_trade)
                    in_trade = False
                    current_trade = None
                    consecutive_losses = 0
                    
                continue
                
            # Not in trade
            if i < cooldown_until:
                continue
                
            # Get pre-calculated score for this index (i - 200 because scores_list starts from i=200)
            score_data = scores_list[i - 200]
            setups = score_data.get('setups', [])
            regime = score_data.get('regime', {})
            
            if not setups:
                continue
            
            # FILTERS
            # Regime Filter
            if filter_regime == "HIGH_VOLATILITY_ONLY":
                if regime.get('volatility_state') != "HIGH_VOLATILITY":
                    continue
            elif filter_regime == "TRENDING_UP_DOWN_AND_RISING_ADX":
                t_state = regime.get('trend_state')
                # Rising ADX proxy: ADX > 25 (or another strong threshold) since we don't have adx_prev cleanly here without pulling from records
                # Let's just pull prev ADX from records
                prev_adx = records[i-1]['adx'] if i > 0 else 0
                curr_adx = candle['adx']
                if t_state not in ["TRENDING_UP", "TRENDING_DOWN"] or curr_adx <= prev_adx:
                    continue
            
            # Session Filter
            dt_time = pd.to_datetime(candle['time'])
            h = dt_time.hour
            if filter_session == "NY_ONLY":
                if h < 13 or h >= 20:
                    continue
            elif filter_session == "LONDON_ONLY":
                if h < 7 or h >= 15:
                    continue
            elif filter_session == "LONDON_AND_NY":
                # Exclude Asian (22:00 - 06:00 UTC), so allow 06:00 to 21:59
                if h >= 22 or h < 6:
                    continue
                    
            # ATR Volatility Filter
            if filter_atr == "MID_ONLY" and atr_percentiles:
                if candle['atr'] < atr_percentiles['p20'] or candle['atr'] > atr_percentiles['p90']:
                    continue
                
            # Find the setup with the highest score (Anti-overlap rule)
            best_setup = max(setups, key=lambda s: s['score'])
            
            # If the winning setup is our target_setup and it meets the threshold
            if best_setup['setup_name'] == target_setup and best_setup['score'] >= threshold and best_setup['direction'] != "NEUTRAL":
                direction = best_setup['direction']
                
                # Direction Filter
                if filter_direction == "BUY_ONLY" and direction != "BUY":
                    continue
                if filter_direction == "SELL_ONLY" and direction != "SELL":
                    continue
                    
                final_score = best_setup['score']
                
                entry_price_bid = candle['close']
                spread_val = self.spread_points * self.point
                
                # Dynamic ATR-based Stop Loss
                sl_price_diff = candle['atr'] * atr_multiplier
                tp_price_diff = sl_price_diff * rr_ratio
                
                if direction == "BUY":
                    entry_price = entry_price_bid + spread_val
                    sl = entry_price - sl_price_diff
                    tp = entry_price + tp_price_diff
                else:
                    entry_price = entry_price_bid
                    sl = entry_price + sl_price_diff
                    tp = entry_price - tp_price_diff
                    
                current_trade = {
                    "timestamp": candle['time'],
                    "direction": direction,
                    "entry_price": entry_price,
                    "sl": sl,
                    "tp": tp,
                    "final_score": final_score,
                    "setup_name": best_setup['setup_name'],
                    "reason": best_setup['reason'],
                    "regime": regime.get('trend_state', 'UNKNOWN')
                }
                in_trade = True

        return trades
