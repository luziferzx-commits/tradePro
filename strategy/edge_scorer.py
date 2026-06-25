import pandas as pd
import numpy as np

class EdgeScorer:
    def __init__(self):
        self.w_trigger = 50.0  # Liquidity
        self.w_location = 30.0 # Premium/Discount
        self.w_context = 20.0  # Structure

    def calculate(self, df):
        res = df.copy()

        # Context Score (20%)
        # BUY Context: UPTREND=1.0, CHOPPY=0.5, DOWNTREND=0.0
        res['context_buy'] = np.where(res['struct_trend'] == 'UPTREND', 1.0,
                             np.where(res['struct_trend'] == 'CHOPPY', 0.5, 0.0))
        
        # SELL Context: DOWNTREND=1.0, CHOPPY=0.5, UPTREND=0.0
        res['context_sell'] = np.where(res['struct_trend'] == 'DOWNTREND', 1.0,
                              np.where(res['struct_trend'] == 'CHOPPY', 0.5, 0.0))

        # Location Score (30%)
        # range_position_pct: 0% is bottom (Discount), 100% is top (Premium)
        if 'range_position_pct' in res.columns:
            res['location_buy'] = np.clip(1.0 - (res['range_position_pct'] / 100.0), 0.0, 1.0)
            res['location_sell'] = np.clip((res['range_position_pct'] / 100.0), 0.0, 1.0)
        else:
            res['location_buy'] = 0.5
            res['location_sell'] = 0.5

        # Trigger Score (50%)
        if 'sweep_swing_low_50' in res.columns:
            res['trigger_buy'] = np.where(res['sweep_swing_low_50'], 1.0,
                                 np.where(res['sweep_daily_low'], 0.2, 0.0))
        else:
            res['trigger_buy'] = 0.0
            
        if 'sweep_swing_high_50' in res.columns:
            res['trigger_sell'] = np.where(res['sweep_swing_high_50'] | res['sweep_daily_high'], 1.0, 0.0)
        else:
            res['trigger_sell'] = 0.0

        # Edge Scores
        res['buy_edge_score'] = (res['context_buy'] * self.w_context) + \
                                (res['location_buy'] * self.w_location) + \
                                (res['trigger_buy'] * self.w_trigger)
                                
        res['sell_edge_score'] = (res['context_sell'] * self.w_context) + \
                                 (res['location_sell'] * self.w_location) + \
                                 (res['trigger_sell'] * self.w_trigger)
                                 
        # Generate Text Reasons
        def get_buy_reason(row):
            trigger_score = int(np.nan_to_num(row['trigger_buy'] * self.w_trigger))
            location_score = int(np.nan_to_num(row['location_buy'] * self.w_location))
            context_score = int(np.nan_to_num(row['context_buy'] * self.w_context))
            total = int(np.nan_to_num(row['buy_edge_score']))
            return f"BUY_EDGE\\nLiquidity: +{trigger_score}\\nDiscount: +{location_score}\\nStructure: +{context_score}\\nTotal: {total}"
            
        def get_sell_reason(row):
            trigger_score = int(np.nan_to_num(row['trigger_sell'] * self.w_trigger))
            location_score = int(np.nan_to_num(row['location_sell'] * self.w_location))
            context_score = int(np.nan_to_num(row['context_sell'] * self.w_context))
            total = int(np.nan_to_num(row['sell_edge_score']))
            return f"SELL_EDGE\\nLiquidity: +{trigger_score}\\nPremium: +{location_score}\\nStructure: +{context_score}\\nTotal: {total}"

        res['buy_edge_reason'] = res.apply(get_buy_reason, axis=1)
        res['sell_edge_reason'] = res.apply(get_sell_reason, axis=1)

        # Clean up intermediate columns
        res.drop(columns=['context_buy', 'context_sell', 'location_buy', 'location_sell', 'trigger_buy', 'trigger_sell'], inplace=True, errors='ignore')

        return res

edge_scorer = EdgeScorer()
