import streamlit as st
import pandas as pd
from dashboard.utils.data_loader import get_pattern_db

st.set_page_config(page_title="Research", page_icon="🔬", layout="wide")
st.title("🔬 Pattern Research Database")

df = get_pattern_db()

if df.empty:
    st.warning("Pattern Database not found or empty.")
    st.stop()

st.write(f"Total Patterns in Database: **{len(df)}**")

st.markdown("---")
st.subheader("Top 10 Patterns by Profit Factor")

# Filter for patterns with decent sample size
min_sample = st.slider("Minimum Sample Size", min_value=10, max_value=200, value=50)

filtered_df = df[df['sample_size'] >= min_sample]
top_10 = filtered_df.sort_values(by="aggregate_pf", ascending=False).head(10)

# Select columns to display
cols_to_show = ['pattern_id', 'aggregate_pf', 'win_rate', 'sample_size', 'aggregate_expectancy_r']

# Format columns
top_10_disp = top_10[cols_to_show].copy()
top_10_disp['aggregate_pf'] = top_10_disp['aggregate_pf'].round(2)
top_10_disp['win_rate'] = (top_10_disp['win_rate'] * 100).round(1).astype(str) + '%'
top_10_disp['aggregate_expectancy_r'] = top_10_disp['aggregate_expectancy_r'].round(3)

st.dataframe(top_10_disp, use_container_width=True)

st.markdown("---")
st.subheader("Raw Database Explorer")
st.dataframe(df, use_container_width=True)
