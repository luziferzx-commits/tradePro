import sqlite3
import pandas as pd

def check_db():
    conn = sqlite3.connect('trades.db')
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cur.fetchall()]
    print("Tables in trades.db:", tables)
    
    if 'trades' in tables:
        df = pd.read_sql("SELECT DISTINCT symbol FROM trades", conn)
        print("Symbols in trades table:")
        print(df['symbol'].tolist())
    else:
        for t in tables:
            df = pd.read_sql(f"SELECT * FROM {t} LIMIT 1", conn)
            print(f"Table {t} columns:", df.columns.tolist())
            if 'symbol' in df.columns:
                symbols = pd.read_sql(f"SELECT DISTINCT symbol FROM {t}", conn)
                print(f"Symbols in {t}:", symbols['symbol'].tolist())
                
if __name__ == '__main__':
    check_db()
