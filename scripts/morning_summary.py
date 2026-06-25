import sqlite3
import pandas as pd
from datetime import datetime, timedelta

def generate_morning_summary():
    try:
        conn = sqlite3.connect('trades.db')
        
        # Get trades from the last 24 hours
        yesterday = (datetime.utcnow() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        query = f"SELECT * FROM trades WHERE open_time >= '{yesterday}'"
        
        try:
            df = pd.read_sql(query, conn)
        except Exception as e:
            # Table might not exist if no trades were ever taken
            df = pd.DataFrame()
            
        conn.close()
        
        if df.empty:
            print("====================================")
            print("🌅 MORNING SUMMARY")
            print("====================================")
            print("No trades were executed overnight.")
            print("The bot was scanning securely but found no high-probability setups.")
            return

        total_trades = len(df)
        wins = len(df[df['pnl'] > 0])
        losses = len(df[df['pnl'] < 0])
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        
        total_pnl = df['pnl'].sum()
        
        print("====================================")
        print("🌅 MORNING SUMMARY")
        print("====================================")
        print(f"Total Trades Taken : {total_trades}")
        print(f"Winning Trades     : {wins}")
        print(f"Losing Trades      : {losses}")
        print(f"Win Rate           : {win_rate:.1f}%")
        print(f"Total PnL          : ${total_pnl:.2f}")
        print("------------------------------------")
        
        # Group by symbol
        print("Performance by Asset:")
        symbol_group = df.groupby('symbol')['pnl'].sum()
        for symbol, pnl in symbol_group.items():
            print(f"  - {symbol}: ${pnl:.2f}")
            
    except Exception as e:
        print(f"Error generating summary: {e}")

if __name__ == '__main__':
    generate_morning_summary()
