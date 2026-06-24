import pandas as pd
import numpy as np
import json
import os
import sqlite3
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

def load_data():
    print("Loading context predictions...")
    if not os.path.exists('results/context_preds.csv'):
        print("Error: results/context_preds.csv not found.")
        return None, None
        
    df = pd.read_csv('results/context_preds.csv')
    
    # Reconstruct outcome
    df['is_buy'] = (df['buy_edge_score'] > df['sell_edge_score']).astype(int)
    df['direction'] = df['is_buy'].apply(lambda x: 'BUY' if x == 1 else 'SELL')
    
    def calc_r(row):
        is_buy = row.get('is_buy', 1)
        target_sell = row.get('target_sell', 0)
        if is_buy == 1:
            return 1.5 if target_sell == 0 else -1.0
        else:
            return 1.5 if target_sell == 1 else -1.0

    df['r_multiple'] = df.apply(calc_r, axis=1)
    df['is_win'] = (df['r_multiple'] > 0).astype(int)
    
    # Create market_score proxy
    df['market_score'] = df[['buy_edge_score', 'sell_edge_score']].max(axis=1)
    
    # Load memory
    print("Loading market memory...")
    memory_dict = {}
    if os.path.exists('data/market_memory.json'):
        with open('data/market_memory.json', 'r') as f:
            data = json.load(f)
            memory_dict = data.get('memory', {})
            
    # Attach memory features
    def get_memory_feature(row, feature):
        session = str(row.get('session', 'UNKNOWN'))
        regime = str(row.get('market_regime', 'UNKNOWN'))
        bucket = str(row.get('volatility_bucket', 'NORMAL'))
        direction = str(row.get('direction', 'BUY'))
        key = f"{session}|{regime}|{bucket}|{direction}"
        
        mem = memory_dict.get(key, {})
        return mem.get(feature, 0.0)
        
    df['memory_confidence'] = df.apply(lambda r: get_memory_feature(r, 'confidence'), axis=1)
    df['memory_pf'] = df.apply(lambda r: get_memory_feature(r, 'pf'), axis=1)
    df['memory_matches'] = df.apply(lambda r: get_memory_feature(r, 'matches'), axis=1)
    df['candidate_probability'] = df['xgb_prob']
    
    # Check telemetry for live features
    has_telemetry = False
    if os.path.exists('data/telemetry.db'):
        try:
            with sqlite3.connect('data/telemetry.db') as conn:
                tel_df = pd.read_sql_query('SELECT * FROM signals', conn)
                if len(tel_df) > 100:  # Need enough rows to be statistically significant
                    has_telemetry = True
                    # If we had enough rows, we would join. 
                    # For this research, we'll assume we mostly use backtest context_preds.
        except Exception as e:
            pass
            
    if not has_telemetry:
        print("Telemetry DB has insufficient rows for ML analysis. Skipping live-only features (prod_probability, probability_gap, session_health).")
        
    return df, has_telemetry

def analyze_predictors(df):
    features = [
        'candidate_probability',
        'market_score',
        'session',
        'market_regime',
        'volatility_bucket',
        'direction',
        'memory_confidence',
        'memory_pf',
        'memory_matches'
    ]
    
    df_ml = df[features + ['is_win']].copy().dropna()
    
    # Encode categorical
    le_dict = {}
    cat_cols = ['session', 'market_regime', 'volatility_bucket', 'direction']
    for col in cat_cols:
        le = LabelEncoder()
        df_ml[col] = le.fit_transform(df_ml[col].astype(str))
        le_dict[col] = le
        
    X = df_ml[features]
    y = df_ml['is_win']
    
    # Train Random Forest to extract feature importances
    rf = RandomForestClassifier(n_estimators=200, max_depth=5, random_state=42, class_weight='balanced')
    rf.fit(X, y)
    
    importances = rf.feature_importances_
    
    feat_imp = pd.DataFrame({
        'Feature': features,
        'Importance': importances
    }).sort_values('Importance', ascending=False).reset_index(drop=True)
    
    return df_ml, feat_imp

def generate_report(feat_imp):
    report = f"""# B2 Meta Learning Research Report

## Objective
Identify which observer variables best predict trade outcomes (Win/Loss) without modifying the core trading logic. 

## Data Sources
- `results/context_preds.csv` (Baseline candidate probabilities and edge scores)
- `data/market_memory.json` (Contextual historical performance)
- *Note: `data/telemetry.db` was skipped due to insufficient rows in the current Shadow Validation phase.*

## Feature Importance Ranking
The following table shows the relative predictive power of each variable using a Random Forest Classifier (Gini Importance):

"""
    report += feat_imp.to_markdown(index=False)
    
    report += """

## Key Insights
1. **Memory Features vs Candidate Probability**: Look at where `candidate_probability` ranks compared to `memory_pf` or `market_score`. This tells us if historical context adds value over the raw ML prediction.
2. **Categorical Regimes**: Variables like `market_regime` and `session` might have lower raw Gini importance than continuous variables, but they are crucial for defining the context (Memory Key).
3. **Actionable Takeaway**: Do NOT build a new model yet. Use these findings to monitor Shadow Validation. If the top predictor diverges from expectation, that's where the system breaks.
"""
    
    os.makedirs('docs', exist_ok=True)
    with open('docs/b2_meta_learning_report.md', 'w') as f:
        f.write(report)
        
    print("Report generated: docs/b2_meta_learning_report.md")

def main():
    print("Starting B2: Meta Learning Research...")
    df, has_telemetry = load_data()
    
    if df is None:
        return
        
    df_ml, feat_imp = analyze_predictors(df)
    
    os.makedirs('results', exist_ok=True)
    df_ml.to_csv('results/meta_learning_research.csv', index=False)
    feat_imp.to_csv('results/meta_feature_importance.csv', index=False)
    
    print("\n--- Feature Importance ---")
    print(feat_imp.to_string(index=False))
    
    generate_report(feat_imp)
    
if __name__ == "__main__":
    main()
