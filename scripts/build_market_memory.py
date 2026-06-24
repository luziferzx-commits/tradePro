import pandas as pd
import json
import os
from datetime import datetime

CSV_PATH = "results/context_preds.csv"
OUT_PATH = "data/market_memory.json"
THRESHOLD = 0.55

def main():
    print(f"Building Market Memory V2 from {CSV_PATH}...")
    
    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found.")
        return
        
    df = pd.read_csv(CSV_PATH)
    total_rows = len(df)
    
    # 1. Filter by Candidate threshold
    df = df[df['xgb_prob'] >= THRESHOLD].copy()
    signal_count = len(df)
    print(f"Total Rows: {total_rows} | Signals >= {THRESHOLD}: {signal_count}")
    
    # 2. Determine Win/Loss using +1.5R/-1.0R (since no PnL column exists)
    # is_buy -> buy_edge_score > sell_edge_score
    df['is_buy'] = (df['buy_edge_score'] > df['sell_edge_score']).astype(int)
    
    def calc_r(row):
        is_buy = row.get('is_buy', 1)
        target_sell = row.get('target_sell', 0)
        
        if is_buy == 1:
            return 1.5 if target_sell == 0 else -1.0
        else:
            return 1.5 if target_sell == 1 else -1.0

    df['r_multiple'] = df.apply(calc_r, axis=1)
    df['is_win'] = df['r_multiple'] > 0
    df['direction'] = df['is_buy'].apply(lambda x: 'BUY' if x == 1 else 'SELL')
    
    # Rename for grouping
    # Memory Key: session, market_regime (regime), volatility_bucket (atr_bucket), direction
    df = df.rename(columns={
        'market_regime': 'regime',
        'volatility_bucket': 'atr_bucket'
    })
    
    # Fill missing just in case
    df['session'] = df['session'].fillna('UNKNOWN')
    df['regime'] = df['regime'].fillna('UNKNOWN')
    df['atr_bucket'] = df['atr_bucket'].fillna('NORMAL')
    
    # Group By Context
    memory_dict = {}
    
    grouped = df.groupby(['session', 'regime', 'atr_bucket', 'direction'])
    
    for name, group in grouped:
        matches = len(group)
        if matches == 0:
            continue
            
        wins = group['is_win'].sum()
        losses = matches - wins
        
        win_rate = wins / matches
        
        # Calculate PF using gross R
        gross_profit = group[group['r_multiple'] > 0]['r_multiple'].sum()
        gross_loss = abs(group[group['r_multiple'] < 0]['r_multiple'].sum())
        
        pf = gross_profit / gross_loss if gross_loss > 0 else (gross_profit / 0.01) # fallback
        
        # Expectancy
        expectancy = group['r_multiple'].mean()
        
        key = f"{name[0]}|{name[1]}|{name[2]}|{name[3]}"
        memory_dict[key] = {
            "matches": int(matches),
            "win_rate": float(win_rate),
            "pf": float(pf),
            "expectancy": float(expectancy)
        }
        
    # Build Final JSON Structure
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    
    output = {
        "metadata": {
            "source_file": CSV_PATH,
            "built_at": datetime.utcnow().isoformat() + "Z",
            "threshold": THRESHOLD,
            "memory_type": "historical_oos",
            "row_count": total_rows,
            "signal_count": signal_count
        },
        "memory": memory_dict
    }
    
    with open(OUT_PATH, 'w') as f:
        json.dump(output, f, indent=4)
        
    print(f"Memory built! Created {len(memory_dict)} context keys.")

if __name__ == "__main__":
    main()
