import pandas as pd
from research.universal_feature_store import UniversalFeatureStore
from data.mt5_client import mt5_client
from market.session_detector import SessionDetector

from strategy.indicators import IndicatorCalculator

mt5_client.connect()
df = mt5_client.get_historical_data('EURUSD', 'M15', 200)
df = IndicatorCalculator.add_indicators(df)
df_feat = UniversalFeatureStore.extract_features(df, 'EURUSD', 'M15')
current = df_feat.iloc[-1]
session = SessionDetector.detect(current['time'].timestamp())
adx = current['adx']

def get_regime(row):
    if row['ema50'] > row['ema200'] and row['adx'] > 25: return "TREND"
    if row['ema50'] < row['ema200'] and row['adx'] > 25: return "TREND"
    return "RANGE"

regime = get_regime(current)
print(f"Current Session: {session}, Regime: {regime}")

db = pd.read_parquet('data/pattern_store/pattern_database.parquet')
matches = db[(db['symbol']=='EURUSD') & (db['session_label']==session) & (db['regime']==regime)]
print(f"Matches in DB for this exact regime/session: {len(matches)}")
print("Total patterns for EURUSD:", len(db[db['symbol']=='EURUSD']))
