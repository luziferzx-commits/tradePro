class CannibalizationMonitor:
    def __init__(self):
        pass
        
    def detect_overlap(self, desks_signals: dict) -> list:
        """
        The real risk is not correlation — it is hidden competition for the same alpha pocket.
        """
        collisions = []
        
        # We simplify the 3-Layer detection for the simulation
        # 1. Factor Overlap (Mocked via shared strategy type)
        # 2. Trade Overlap (Same timestamp and ticker)
        # 3. Capacity Collision (Competing for same liquidity)
        
        tickers_seen = {}
        
        for desk_id, signal in desks_signals.items():
            ticker = signal['ticker']
            if ticker in tickers_seen:
                # Collision Detected! Two desks are fighting for the same liquidity pool.
                collisions.append({
                    'desk_a': tickers_seen[ticker],
                    'desk_b': desk_id,
                    'ticker': ticker,
                    'reason': 'CAPACITY_COLLISION'
                })
            else:
                tickers_seen[ticker] = desk_id
                
        return collisions
