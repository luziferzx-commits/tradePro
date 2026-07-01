import pandas as pd
import os

def main():
    db_path = 'data/pattern_store/pattern_database.parquet'
    if not os.path.exists(db_path):
        print("Pattern DB not found.")
        return
        
    df = pd.read_parquet(db_path)
    print("Columns:", df.columns.tolist())
    if 'symbol' in df.columns:
        symbols = df['symbol'].unique().tolist()
        print(f"Total symbols in DB: {len(symbols)}")
        print("Symbols list:")
        print(symbols)
    else:
        print("No 'symbol' column in DB.")

if __name__ == '__main__':
    main()
