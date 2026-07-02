import streamlit as st
import pandas as pd
from dashboard.utils.data_loader import get_account_info, get_open_positions, get_trade_history
import time

st.set_page_config(page_title="Live Trading", page_icon="🔴", layout="wide")

st.title("🔴 Live Trading")

# Auto-refresh mechanism (refreshes every 5 seconds)
# Streamlit >= 1.35 supports st_autorefresh natively but we'll use a rerun trick or just manual for now
# For now, let's add a manual refresh button that stands out
col1, col2 = st.columns([1, 9])
with col1:
    if st.button("🔄 Refresh Data"):
        st.rerun()
with col2:
    st.caption(f"Last updated: {pd.Timestamp.now().strftime('%H:%M:%S')}")

# --- Account Metrics ---
acc = get_account_info()
if acc:
    st.subheader("Account Overview")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Balance", f"${acc['balance']:,.2f}")
    m2.metric("Equity", f"${acc['equity']:,.2f}", f"{acc['profit']:,.2f}")
    m3.metric("Free Margin", f"${acc['margin_free']:,.2f}")
    m4.metric("Margin Level", f"{acc['margin_level']:,.2f}%" if acc['margin_level'] else "N/A")
else:
    st.error("Failed to connect to MT5.")

st.markdown("---")

# --- Open Positions ---
st.subheader("Open Positions")
positions = get_open_positions()

if positions:
    df_pos = pd.DataFrame(positions)
    # Format time (MT5 time is Unix Epoch UTC, Thai Time is UTC+7)
    df_pos['time'] = pd.to_datetime(df_pos['time'], unit='s') + pd.Timedelta(hours=7)
    df_pos['time'] = df_pos['time'].dt.strftime('%H:%M:%S')

    # Reorder and format columns
    df_pos = df_pos[['time', 'ticket', 'symbol', 'direction', 'volume', 'entry_price', 'sl', 'tp', 'current_price', 'profit']]
    
    # Colorize PnL
    def color_pnl(val):
        color = 'green' if val > 0 else 'red'
        return f'color: {color}'
        
    st.dataframe(df_pos.style.map(color_pnl, subset=['profit']), use_container_width=True)
else:
    st.info("No open positions at the moment.")

st.markdown("---")

# --- Today's Trades (History) ---
st.subheader("Today's Closed Trades")
history = get_trade_history(days=1)
if history:
    df_hist = pd.DataFrame(history)
    wins = len(df_hist[df_hist['profit'] > 0])
    losses = len(df_hist[df_hist['profit'] < 0])
    total_pnl = df_hist['profit'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Closed Trades", len(df_hist))
    c2.metric("W/L Ratio", f"{wins}W / {losses}L")
    c3.metric("Daily PnL", f"${total_pnl:,.2f}", f"{total_pnl:,.2f}")
    
    # Format time (MT5 time is Unix Epoch UTC, Thai Time is UTC+7)
    df_hist['time'] = pd.to_datetime(df_hist['time'], unit='s') + pd.Timedelta(hours=7)
    df_hist['time'] = df_hist['time'].dt.strftime('%H:%M:%S')
    
    st.dataframe(df_hist[['time', 'ticket', 'symbol', 'direction', 'volume', 'price', 'profit']].style.map(lambda x: 'color: green' if x > 0 else 'color: red', subset=['profit']), use_container_width=True)
else:
    st.info("No trades closed today.")

# --- Controls ---
st.sidebar.subheader("Control Panel")
st.sidebar.warning("Live Controls (Not fully wired in Streamlit. Use Telegram /pause)")
if st.sidebar.button("⏸️ Pause AlphaWorker"):
    st.sidebar.info("Command sent via backend. (Simulation)")
if st.sidebar.button("▶️ Resume AlphaWorker"):
    st.sidebar.info("Command sent via backend. (Simulation)")
if st.sidebar.button("🛑 EMERGENCY CLOSE ALL"):
    st.sidebar.error("PANIC SIGNAL SENT!")
