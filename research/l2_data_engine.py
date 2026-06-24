import pandas as pd
import numpy as np

class L2DataEngine:
    def __init__(self):
        pass
        
    def calculate_obi(self, bid_volume: float, ask_volume: float) -> float:
        """
        Order Book Imbalance (OBI)
        Values approach +1 for heavy bid pressure, -1 for heavy ask pressure.
        """
        total_vol = bid_volume + ask_volume
        if total_vol == 0:
            return 0.0
        return (bid_volume - ask_volume) / total_vol
        
    def calculate_microprice(self, bid_price: float, bid_volume: float, ask_price: float, ask_volume: float) -> float:
        """
        Volume-weighted midprice proxy. Better than simple midprice because it leans
        towards the side with less liquidity (since that side is more likely to be consumed).
        Actually standard microprice:
        Microprice = (AskPrice * BidVol + BidPrice * AskVol) / (BidVol + AskVol)
        """
        total_vol = bid_volume + ask_volume
        if total_vol == 0:
            return (bid_price + ask_price) / 2.0
            
        return ((ask_price * bid_volume) + (bid_price * ask_volume)) / total_vol
        
    def process_tick(self, tick: dict) -> dict:
        """
        Takes raw L2 tick and returns enriched microstructural state
        """
        obi = self.calculate_obi(tick['bid_vol_l1'], tick['ask_vol_l1'])
        microprice = self.calculate_microprice(tick['bid_price_l1'], tick['bid_vol_l1'], 
                                               tick['ask_price_l1'], tick['ask_vol_l1'])
                                               
        midprice = (tick['bid_price_l1'] + tick['ask_price_l1']) / 2.0
        
        return {
            'timestamp': tick['timestamp'],
            'midprice': midprice,
            'microprice': microprice,
            'obi': obi,
            'spread': tick['ask_price_l1'] - tick['bid_price_l1']
        }
