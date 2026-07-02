import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd

def main():
    if not mt5.initialize():
        print("Fail")
        return
        
    start_date = datetime.now() - timedelta(days=30)
    deals = mt5.history_deals_get(start_date, datetime.now())
    if not deals:
        print("No deals found in history.")
        mt5.shutdown()
        return
        
    history = []
    for d in deals:
        # We look at exit deals to sum profit
        if d.entry == mt5.DEAL_ENTRY_OUT:
            history.append({
                'symbol': d.symbol,
                'profit': d.profit,
                'volume': d.volume,
                'magic': d.magic,
                'comment': d.comment,
                'type': 'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL'
            })
            
    df = pd.DataFrame(history)
    if df.empty:
        print("No exit deals found.")
        mt5.shutdown()
        return
        
    print("=== PnL and Trade Count by Magic Number ===")
    summary = df.groupby('magic').agg(
        total_pnl=('profit', 'sum'),
        trade_count=('profit', 'count'),
        avg_profit=('profit', 'mean')
    ).reset_index()
    
    # Map magic numbers
    magic_map = {
        234000: "GQOS Bot (234000)",
        0: "Manual Trades / Other EA (0)"
    }
    summary['name'] = summary['magic'].map(lambda m: magic_map.get(m, f"Other Magic ({m})"))
    print(summary.to_string(index=False))
    
    print("\n=== Top 10 Largest Losses ===")
    print(df.sort_values('profit').head(10).to_string(index=False))
    
    mt5.shutdown()

if __name__ == '__main__':
    main()
