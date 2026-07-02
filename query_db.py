import sqlite3
import pandas as pd
try:
    conn = sqlite3.connect('trades.db')
    df = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
    print("Tables:", df['name'].tolist())
    
    if 'trades' in df['name'].tolist():
        df_trades = pd.read_sql_query("SELECT * FROM trades ORDER BY id DESC LIMIT 5", conn)
        print("Recent Trades in trades.db:")
        print(df_trades.to_string())
        
    conn.close()
    
    conn2 = sqlite3.connect('gqos_research.db')
    df2 = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn2)
    print("\nTables in research DB:", df2['name'].tolist())
    
    if 'model_training_jobs' in df2['name'].tolist():
         print("Found model_training_jobs")
         
    conn2.close()
except Exception as e:
    print(f"Error: {e}")
