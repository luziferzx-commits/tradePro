import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Learning Loop", page_icon="🧠", layout="wide")
st.title("🧠 Self-Learning Loop Progress")

# Fetch Pending Trades for Retrain Trigger
try:
    with open("data/learning/pending_trades.json", "r") as f:
        pending_trades = json.load(f)
        pending_count = len(pending_trades)
except:
    pending_count = 0

retrain_threshold = 50

st.subheader("Retrain Trigger Progress")
st.progress(min(pending_count / retrain_threshold, 1.0))
st.write(f"**{pending_count} / {retrain_threshold}** trades recorded before next Retrain & Model Promotion")

st.markdown("---")

# Display Candidates vs Production Models
st.subheader("Model Versions")

def list_models(status):
    dir_path = f"models/{status}"
    if not os.path.exists(dir_path): return []
    return [f for f in os.listdir(dir_path) if f.endswith('.pkl')]

prod_models = list_models("production")
cand_models = list_models("candidate")

col1, col2 = st.columns(2)
with col1:
    st.markdown("### 🚀 Production Models")
    if prod_models:
        for m in prod_models:
            st.code(m)
    else:
        st.info("No production models found.")

with col2:
    st.markdown("### 🧪 Candidate Models (Training)")
    if cand_models:
        for m in cand_models:
            st.code(m)
    else:
        st.info("No candidate models found.")
