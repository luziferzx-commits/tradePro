import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd
mt5.initialize()
today = datetime.now() - timedelta(days=1)
deals = mt5.history_deals_get(today, datetime.now())
if deals:
    history = []
    for d in deals:
        if d.entry == mt5.DEAL_ENTRY_OUT:
            history.append({
                'symbol': d.symbol,
                'profit': d.profit,
                'volume': d.volume,
                'type': 'SELL' if d.type == mt5.DEAL_TYPE_SELL else 'BUY'
            })
    df = pd.DataFrame(history)
    print(f'Total PnL: {df["profit"].sum()}')
    print('--- Top 5 Worst Trades ---')
    print(df.sort_values('profit').head(5).to_string(index=False))
