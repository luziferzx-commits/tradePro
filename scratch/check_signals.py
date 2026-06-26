import sqlite3
import pandas as pd

def check_rejections():
    conn = sqlite3.connect('trades.db')
    
    symbols_to_check = ['GBPUSD', 'AUDUSD', 'USDCAD', 'NZDUSD', 'EURGBP', 'AUDCAD', 'NAS100', 'USTEC', 'GER40', 'SOLUSD', 'XRPUSD', 'USOIL', 'GBPUSDm', 'AUDUSDm', 'USDCADm', 'NZDUSDm', 'EURGBPm', 'AUDCADm', 'USTECm', 'GER40m', 'SOLUSDm', 'XRPUSDm', 'USOILm']
    
    query = """
    SELECT m.symbol, ts.direction, ts.ml_rejected, ts.ml_rejection_reason, ts.ai_approved, ts.ai_reason 
    FROM trade_signals ts 
    JOIN market_states m ON ts.market_state_id = m.id 
    WHERE m.symbol IN ({})
    """.format(','.join('?' * len(symbols_to_check)))
    
    try:
        df = pd.read_sql(query, conn, params=symbols_to_check)
        if df.empty:
            print("No signals found in trade_signals table for these symbols.")
            
            # Check market_states directly to see if they are even being scanned
            query_m = "SELECT symbol, count(*) as count FROM market_states WHERE symbol IN ({}) GROUP BY symbol".format(','.join('?' * len(symbols_to_check)))
            df_m = pd.read_sql(query_m, conn, params=symbols_to_check)
            if df_m.empty:
                print("These symbols are not even being scanned (not in market_states).")
            else:
                print("Symbols are being scanned, but no signals are generated for them:")
                print(df_m)
        else:
            print("Signals found for these symbols:")
            print(df.groupby(['symbol', 'ml_rejected', 'ml_rejection_reason', 'ai_approved', 'ai_reason']).size().reset_index(name='count'))
    except Exception as e:
        print("Error:", e)
        
if __name__ == '__main__':
    check_rejections()
