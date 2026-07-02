import unittest
import pandas as pd
import numpy as np
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from strategy.market_structure import MarketStructure

class TestMarketStructure(unittest.TestCase):
    def test_market_structure(self):
        # Create a mock dataframe of prices
        # Let's build an explicit uptrend
        # 1. Swing Low at index 5 (val 10)
        # 2. Swing High at index 15 (val 50)
        # 3. Swing Low at index 25 (val 20) -> HL
        # 4. Swing High at index 35 (val 60) -> HH
        
        prices = []
        # Uptrend zigzag: 10 -> 50 -> 20 -> 60
        prices = []
        for i in range(50):
            if i <= 5: prices.append(20 - i*2) # 0->20, 5->10
            elif i <= 15: prices.append(10 + (i-5)*4) # 5->10, 15->50
            elif i <= 25: prices.append(50 - (i-15)*3) # 15->50, 25->20
            elif i <= 35: prices.append(20 + (i-25)*4) # 25->20, 35->60
            else: prices.append(60 - (i-35)*1) # 35->60, down
                
        df = pd.DataFrame({
            'high': prices,
            'low': prices,
            'close': prices
        })
        
        ms = MarketStructure(left_bars=2, right_bars=2)
        res = ms.calculate(df)
        
        # At index 5, is_swing_low should be True
        self.assertTrue(res['is_swing_low'].iloc[5])
        
        # At index 15, is_swing_high should be True
        self.assertTrue(res['is_swing_high'].iloc[15])
        
        # At index 25, is_swing_low should be True
        self.assertTrue(res['is_swing_low'].iloc[25])
        
        # At index 35, is_swing_high should be True
        self.assertTrue(res['is_swing_high'].iloc[35])
        
        # Confirmation happens at i + right_bars (e.g. index 35 is confirmed at 37)
        # So at index 38, known_last_swing_high should be 60, known_prev_swing_high should be 50 -> struct_hh = True
        # known_last_swing_low should be 20, known_prev_swing_low should be 10 -> struct_hl = True
        # Trend should be UPTREND
        
        self.assertEqual(res['known_last_swing_high'].iloc[38], 60)
        self.assertEqual(res['known_prev_swing_high'].iloc[38], 50)
        
        self.assertEqual(res['known_last_swing_low'].iloc[38], 20)
        self.assertEqual(res['known_prev_swing_low'].iloc[38], 10)
        
        self.assertTrue(res['struct_hh'].iloc[38])
        self.assertTrue(res['struct_hl'].iloc[38])
        self.assertEqual(res['struct_trend'].iloc[38], "UPTREND")
        
        # At index 38: close = 57.0
        # known_last_swing_high = 60.0, known_prev_swing_high = 50.0
        # known_last_swing_low = 20.0
        
        # struct_strength = (60-50)/50 * 100 = 20.0
        self.assertEqual(res['struct_strength'].iloc[38], 20.0)
        
        # distance_to_last_HH = (60-57)/57 * 100 = 5.26315789...
        self.assertAlmostEqual(res['distance_to_last_HH'].iloc[38], 5.2631, places=3)
        
        # distance_to_last_LL = (57-20)/57 * 100 = 64.91228...
        self.assertAlmostEqual(res['distance_to_last_LL'].iloc[38], 64.9122, places=3)
        
        # distance_to_breakout_level = (57-50)/57 * 100 = 12.2807...
        self.assertAlmostEqual(res['distance_to_breakout_level'].iloc[38], 12.2807, places=3)

if __name__ == '__main__':
    unittest.main()
