import streamlit as st
import plotly.graph_objects as go
from dashboard.utils.data_loader import get_account_info, get_open_positions
import pandas as pd

st.set_page_config(page_title="Risk Monitor", page_icon="🛡️", layout="wide")
st.title("🛡️ Risk Monitor")

acc = get_account_info()
if not acc:
    st.warning("Failed to connect to MT5.")
    st.stop()

st.subheader("Margin Usage")
margin_used = acc['margin']
margin_free = acc['margin_free']
total_equity = acc['equity']

fig = go.Figure(go.Indicator(
    mode = "gauge+number",
    value = margin_used,
    domain = {'x': [0, 1], 'y': [0, 1]},
    title = {'text': "Margin Used ($)"},
    gauge = {
        'axis': {'range': [None, total_equity]},
        'bar': {'color': "darkred"},
        'steps': [
            {'range': [0, total_equity * 0.1], 'color': "lightgray"},
            {'range': [total_equity * 0.1, total_equity * 0.5], 'color': "orange"},
            {'range': [total_equity * 0.5, total_equity], 'color': "red"}],
        'threshold': {
            'line': {'color': "red", 'width': 4},
            'thickness': 0.75,
            'value': total_equity * 0.8}
    }
))
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

st.subheader("Total Exposure by Symbol")
positions = get_open_positions()
if positions:
    df = pd.DataFrame(positions)
    # Aggregate volume by symbol
    exposure = df.groupby('symbol')['volume'].sum().reset_index()
    
    fig2 = go.Figure(data=[go.Pie(labels=exposure['symbol'], values=exposure['volume'], hole=.3)])
    fig2.update_layout(template="plotly_dark")
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("No active exposure.")
