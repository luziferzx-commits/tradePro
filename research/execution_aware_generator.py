import pandas as pd
import numpy as np

class ExecutionAwareGenerator:
    def __init__(self, min_move_atr_multiple=5.0, min_holding_bars=10):
        self.min_move_atr_multiple = min_move_atr_multiple
        self.min_holding_bars = min_holding_bars
        self.feature_conditions = {}
        
    def filter_regimes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        HARD REJECT 'HIGH_VOL_EXPANSION'
        Only keep 'LOW_VOL_COMPRESSION' and 'NORMAL_VOLATILITY'
        """
        valid_regimes = ['LOW_VOL_COMPRESSION', 'NORMAL_VOLATILITY']
        if 'regime_label' in df.columns:
            return df[df['regime_label'].isin(valid_regimes)].copy()
        return df

    def generate_structural_templates(self, df: pd.DataFrame):
        """
        Only allow:
        - regime shift trades
        - compression breakout structures
        - volatility expansion continuation
        (Tick scalping is strictly ignored)
        """
        print("Generating Execution-Aware Hypothesis Templates...")
        
        # Example: Compression Breakout Structure
        # Condition: CVD increasing while in LOW_VOL_COMPRESSION, expecting a breakout
        if 'cvd' in df.columns and 'atr' in df.columns:
            # Structurally, we look for CVD trend > 0
            cvd_trend = df['cvd'].diff(12).fillna(0) > 0
            self.feature_conditions['COMPRESSION_CVD_BREAKOUT_LONG'] = cvd_trend
            self.feature_conditions['COMPRESSION_CVD_BREAKOUT_SHORT'] = ~cvd_trend
            
        # Add more structural templates here...
        # For simulation, we add a mock strong signal
        self.feature_conditions['STRUCTURAL_MOMENTUM'] = df['close'] > df['close'].shift(24)

    def validate_execution_edge(self, df: pd.DataFrame, condition_name: str, regime: str, fwd_return_col: str='fwd_ret_24') -> dict:
        """
        Condition C: ExpectedMove >= (5 * ATR)
        """
        mask = (df['regime_label'] == regime) & self.feature_conditions.get(condition_name, False)
        subset = df[mask]
        
        if len(subset) < 30:
            return None
            
        mean_ret = subset[fwd_return_col].mean()
        avg_atr_pct = (subset['atr'] / subset['close']).mean() if 'atr' in subset.columns else 0.0005
        
        # Expected move constraint (Absolute move)
        expected_move_pct = abs(mean_ret)
        required_move_pct = self.min_move_atr_multiple * avg_atr_pct
        
        if expected_move_pct >= required_move_pct:
            return {
                'condition': condition_name,
                'regime': regime,
                'expected_return': mean_ret,
                'hit_rate': (subset[fwd_return_col] > 0).mean() if mean_ret > 0 else (subset[fwd_return_col] < 0).mean(),
                'survives_friction': True,
                'trade_count': len(subset)
            }
        return None
