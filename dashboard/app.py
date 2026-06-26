import streamlit as st
import sys
import os

# Add root project dir to path so we can import gqos modules if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

st.set_page_config(
    page_title="GQOS Institutional Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark mode and styling
st.markdown("""
<style>
    /* Metric styling */
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
    }
    div[data-testid="stMetricDelta"] {
        font-size: 1.2rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("📈 GQOS Terminal")
st.markdown("Welcome to the GQOS Live Institutional Dashboard. Select a view from the sidebar.")

st.info("👈 Use the sidebar to navigate between Live Trading, Performance, and Risk metrics.")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("GQOS Core Engine v2.1")
st.sidebar.caption("Status: ONLINE")
