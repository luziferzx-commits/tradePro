import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
from dashboard.utils.data_loader import get_ledger_stats

st.set_page_config(page_title="Performance", page_icon="📈", layout="wide")
st.title("📈 Performance Metrics")

ledger = get_ledger_stats()
if not ledger:
    st.warning("No ledger data found.")
    st.stop()

# Basic Metrics
st.subheader("Global Performance")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total PnL", f"${ledger.get('realized_pnl', 0):,.2f}")
c2.metric("Total Trades", ledger.get('total_trades', 0))
win_rate = ledger.get('win_rate', 0)
c3.metric("Win Rate", f"{win_rate:.2f}%")
c4.metric("Profit Factor", f"{ledger.get('profit_factor', 0):.2f}")

st.markdown("---")

# Draw Equity Curve mock/placeholder if we don't have time series in ledger
st.subheader("Equity Curve (Simulation / Last 30 Trades)")

try:
    with open("data/learning/pending_trades.json", "r") as f:
        pass # Placeholder for actual historical trades parsing
    
    # Mock data for demonstration if historical not available
    import numpy as np
    np.random.seed(42)
    pnl_sequence = np.random.normal(10, 50, 100).cumsum()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=pnl_sequence, mode='lines', name='Equity', line=dict(color='#00ff88', width=3)))
    fig.update_layout(
        title="Simulated Equity Curve",
        xaxis_title="Trades",
        yaxis_title="Cumulative PnL ($)",
        template="plotly_dark",
        margin=dict(l=0, r=0, t=40, b=0)
    )
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.error(f"Could not load equity curve: {e}")

st.markdown("---")

# Session Analysis Placeholder
st.subheader("Session Analysis")
st.info("Detailed session breakdown requires parsing database.")
