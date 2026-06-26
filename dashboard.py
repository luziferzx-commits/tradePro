"""
dashboard.py — GQOS TradePro Pattern Promotion Dashboard
รัน: streamlit run dashboard.py
 
Pages:
  1. Overview       — PnL, win rate, pattern health
  2. Pattern DB     — scatter, top edges, filterable table
  3. Live Outcomes  — recent trades, symbol performance
"""
import os
import sys
import json
import warnings
warnings.filterwarnings("ignore")
 
sys.path.insert(0, os.path.abspath("."))
 
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
 
# ── Page config ────────────────────────────────────────────────
st.set_page_config(
    page_title="GQOS TradePro",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)
 
# ── Dark quant theme ───────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
 
  html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background: #0a0e1a;
    color: #e2e8f0;
  }
  .stApp { background: #0a0e1a; }
 
  /* Metric cards */
  [data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.8rem !important;
    color: #38bdf8 !important;
  }
  [data-testid="stMetricDelta"] { font-size: 0.85rem !important; }
 
  /* Sidebar */
  section[data-testid="stSidebar"] {
    background: #0f1629 !important;
    border-right: 1px solid #1e2d4a;
  }
 
  /* Headers */
  h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; color: #38bdf8; }
  h1 { font-size: 1.5rem; letter-spacing: 0.05em; }
 
  /* Divider */
  hr { border-color: #1e2d4a; }
 
  /* Promotion badges */
  .badge-validated   { color: #4ade80; font-weight: 600; }
  .badge-discovered  { color: #facc15; font-weight: 600; }
  .badge-rejected    { color: #f87171; }
  .badge-approved    { color: #818cf8; font-weight: 600; }
  .badge-demoted     { color: #6b7280; }
 
  /* Promotion flow */
  .promo-flow {
    display: flex; gap: 8px; align-items: center;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.8rem; margin-bottom: 1rem;
    padding: 8px 12px; background: #0f1629;
    border: 1px solid #1e2d4a; border-radius: 6px;
  }
  .promo-step { padding: 2px 8px; border-radius: 4px; }
  .ps-rejected   { background: #1f1010; color: #f87171; }
  .ps-discovered { background: #1f1a08; color: #facc15; }
  .ps-validated  { background: #0a1f12; color: #4ade80; }
  .ps-shadow     { background: #0d1625; color: #60a5fa; }
  .ps-approved   { background: #130f2a; color: #818cf8; }
  .ps-live       { background: #1a0d1a; color: #e879f9; }
  .arrow { color: #475569; }
</style>
""", unsafe_allow_html=True)
 
# ── Data loaders ───────────────────────────────────────────────
PATTERN_DB_PATH = "data/pattern_store/pattern_database.parquet"
OUTCOMES_PATH   = "data/learning/live_outcomes.jsonl"
SLIPPAGE_PATH   = "data/learning/slippage_log.jsonl"

@st.cache_data(ttl=30)
def load_slippage():
    if not os.path.exists(SLIPPAGE_PATH):
        return pd.DataFrame()
    rows = []
    with open(SLIPPAGE_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.DataFrame(rows) if rows else pd.DataFrame()

@st.cache_data(ttl=60)
def load_pattern_db():
    if not os.path.exists(PATTERN_DB_PATH):
        return pd.DataFrame()
    return pd.read_parquet(PATTERN_DB_PATH)
 
@st.cache_data(ttl=30)
def load_outcomes():
    if not os.path.exists(OUTCOMES_PATH):
        return pd.DataFrame()
    rows = []
    with open(OUTCOMES_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "close_time" in df.columns:
        df["close_time"] = pd.to_datetime(df["close_time"])
    return df
 
def load_mt5_positions():
    try:
        import MetaTrader5 as mt5
        if not mt5.terminal_info():
            mt5.initialize()
        acc = mt5.account_info()
        pos = mt5.positions_get() or []
        return acc, pos
    except Exception:
        return None, []
 
def promo_color(status: str) -> str:
    m = {
        "LIVE_APPROVED":       "#818cf8",
        "SHADOW_PASSED":       "#60a5fa",
        "RESEARCH_VALIDATED":  "#4ade80",
        "RESEARCH_DISCOVERED": "#facc15",
        "DEMOTED":             "#6b7280",
        "REJECTED":            "#f87171",
    }
    return m.get(status, "#94a3b8")
 
# ── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 GQOS TradePro")
    st.markdown("---")
    page = st.radio(
        "Navigation",
        ["📊 Overview", "🧠 Pattern Knowledge Base", "📈 Live Outcomes"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
 
    st.markdown("---")
    st.markdown(
        "<small style='color:#475569'>Auto-refresh: 60s<br>"
        f"Last updated: {datetime.now().strftime('%H:%M:%S')}</small>",
        unsafe_allow_html=True,
    )
 
# ── Promotion flow header ──────────────────────────────────────
st.markdown("""
<div class="promo-flow">
  <span class="promo-step ps-rejected">REJECTED</span>
  <span class="arrow">→</span>
  <span class="promo-step ps-discovered">RESEARCH_DISCOVERED</span>
  <span class="arrow">→</span>
  <span class="promo-step ps-validated">RESEARCH_VALIDATED</span>
  <span class="arrow">→</span>
  <span class="promo-step ps-shadow">SHADOW_PASSED</span>
  <span class="arrow">→</span>
  <span class="promo-step ps-approved">LIVE_APPROVED</span>
</div>
""", unsafe_allow_html=True)
 
df_pat = load_pattern_db()
df_out = load_outcomes()
 
# ══════════════════════════════════════════════════════════════
# PAGE 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════
if page == "📊 Overview":
    st.markdown("# 📊 Overview")
 
    # ── Live account ──────────────────────────────────────────
    acc, pos = load_mt5_positions()
    col1, col2, col3, col4, col5 = st.columns(5)
 
    if acc:
        daily_pnl = sum(p.profit for p in pos) if pos else 0.0
        with col1:
            st.metric("Balance", f"${acc.balance:,.2f}")
        with col2:
            delta_eq = acc.equity - acc.balance
            st.metric("Equity", f"${acc.equity:,.2f}",
                      delta=f"{delta_eq:+.2f}")
        with col3:
            st.metric("Open Positions", len(pos))
        with col4:
            pnl_sign = "+" if daily_pnl >= 0 else ""
            st.metric("Floating PnL", f"{pnl_sign}{daily_pnl:.2f}",
                      delta=f"{daily_pnl/acc.balance*100:+.2f}%")
        with col5:
            margin_pct = acc.margin / acc.balance * 100 if acc.balance > 0 else 0
            st.metric("Margin Used", f"{margin_pct:.1f}%")
    else:
        st.info("MT5 not connected — showing pattern stats only")
 
    st.markdown("---")
    
    # ── Macro & System Status ─────────────────────────────────
    st.markdown("### 🌐 Macro & System Status")
    c_m1, c_m2, c_m3 = st.columns(3)
    
    with c_m1:
        try:
            from strategy.crypto_sentiment import CryptoSentiment
            fng = CryptoSentiment.get_fear_greed_index()
            # If extreme, color the text
            f_color = "normal"
            if fng['value'] < 25 or fng['value'] > 75:
                f_color = "inverse"
            st.metric("Fear & Greed Index", f"{fng['value']} / 100", delta=fng['label'], delta_color=f_color)
        except Exception:
            st.metric("Fear & Greed Index", "N/A")
            
    with c_m2:
        trades_done = len(df_out)
        progress = trades_done % 50
        st.metric("Retrain Progress", f"{progress} / 50", delta=f"{50 - progress} trades until next retrain", delta_color="off")
        
    with c_m3:
        try:
            from strategy.cot_analyzer import COTAnalyzer
            cot_pos = COTAnalyzer.get_net_position("XAUUSD")
            if cot_pos:
                st.metric("COT: Gold (Hedge Funds)", cot_pos['direction'], delta=f"Net: {cot_pos['net_position']:,}", delta_color="normal" if cot_pos['direction']=="BULLISH" else "inverse")
            else:
                st.metric("COT: Gold", "N/A")
        except Exception:
            st.metric("COT: Gold", "N/A")

    st.markdown("---")
 
    # ── Live outcomes stats ───────────────────────────────────
    col_a, col_b, col_c, col_d = st.columns(4)
    if not df_out.empty:
        wins   = len(df_out[df_out["outcome"] == "WIN"])
        losses = len(df_out[df_out["outcome"] == "LOSS"])
        total  = len(df_out)
        wr     = wins / total * 100 if total > 0 else 0
        total_pnl = df_out["realized_pnl"].sum() if "realized_pnl" in df_out else 0
        avg_r  = df_out["actual_r"].dropna().mean() if "actual_r" in df_out else 0
 
        with col_a: st.metric("Live Trades", total)
        with col_b: st.metric("Win Rate", f"{wr:.1f}%",
                              delta=f"{wins}W {losses}L")
        with col_c: st.metric("Total PnL", f"${total_pnl:+.2f}")
        with col_d: st.metric("Avg R", f"{avg_r:.2f}R")
    else:
        with col_a: st.metric("Live Trades", 0)
        with col_b: st.metric("Win Rate", "—")
        with col_c: st.metric("Total PnL", "$0.00")
        with col_d: st.metric("Avg R", "—")
 
    st.markdown("---")
    col_left, col_right = st.columns([2, 1])
 
    # ── PnL Curve ─────────────────────────────────────────────
    with col_left:
        st.markdown("### Cumulative PnL")
        if not df_out.empty and "realized_pnl" in df_out.columns:
            df_curve = df_out.sort_values("close_time").copy()
            df_curve["cumulative_pnl"] = df_curve["realized_pnl"].cumsum()
            fig = px.area(
                df_curve, x="close_time", y="cumulative_pnl",
                color_discrete_sequence=["#38bdf8"],
                template="plotly_dark",
            )
            fig.update_layout(
                paper_bgcolor="#0a0e1a", plot_bgcolor="#0f1629",
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis_title="", yaxis_title="USD",
                showlegend=False,
            )
            fig.update_traces(line_color="#38bdf8", fillcolor="rgba(56,189,248,0.15)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No live outcomes yet — start trading to see PnL curve")
 
    # ── Pattern Health Donut ──────────────────────────────────
    with col_right:
        st.markdown("### Pattern Health")
        if not df_pat.empty:
            promo_counts = df_pat["promotion_status"].value_counts().reset_index()
            promo_counts.columns = ["status", "count"]
            colors = [promo_color(s) for s in promo_counts["status"]]
            fig = go.Figure(go.Pie(
                labels=promo_counts["status"],
                values=promo_counts["count"],
                hole=0.6,
                marker_colors=colors,
                textinfo="none",
                hovertemplate="%{label}<br>%{value:,} patterns<extra></extra>",
            ))
            fig.update_layout(
                paper_bgcolor="#0a0e1a",
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(
                    font=dict(color="#94a3b8", size=11),
                    bgcolor="rgba(0,0,0,0)",
                ),
                annotations=[dict(
                    text=f"<b>{len(df_pat):,}</b><br>patterns",
                    font=dict(color="#38bdf8", size=14, family="IBM Plex Mono"),
                    showarrow=False,
                )],
            )
            st.plotly_chart(fig, use_container_width=True)
 
    # ── Open Positions ────────────────────────────────────────
    if pos:
        st.markdown("### Open Positions")
        rows = []
        for p in pos:
            rows.append({
                "Symbol":    p.symbol,
                "Side":      "BUY" if p.type == 0 else "SELL",
                "Lot":       p.volume,
                "Entry":     p.price_open,
                "SL":        p.sl,
                "TP":        p.tp,
                "PnL":       f"${p.profit:+.2f}",
            })
        df_pos = pd.DataFrame(rows)
        st.dataframe(
            df_pos.style.map(
                lambda v: "color: #4ade80" if isinstance(v, str) and "+" in v
                else ("color: #f87171" if isinstance(v, str) and "-" in v else ""),
                subset=["PnL"]
            ),
            use_container_width=True, hide_index=True,
        )
 
# ══════════════════════════════════════════════════════════════
# PAGE 2 — PATTERN KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════
elif page == "🧠 Pattern Knowledge Base":
    st.markdown("# 🧠 Pattern Knowledge Base")
 
    if df_pat.empty:
        st.error("Pattern database not found at: " + PATTERN_DB_PATH)
        st.stop()
 
    # ── Filters ───────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        symbols = ["All"] + sorted(df_pat["symbol"].unique().tolist())
        sel_sym = st.selectbox("Symbol", symbols)
    with col_f2:
        statuses = ["All"] + sorted(df_pat["promotion_status"].unique().tolist())
        sel_status = st.selectbox("Promotion Status", statuses)
    with col_f3:
        directions = ["All", "LONG", "SHORT"]
        sel_dir = st.selectbox("Direction", directions)
 
    df_f = df_pat.copy()
    if sel_sym    != "All": df_f = df_f[df_f["symbol"] == sel_sym]
    if sel_status != "All": df_f = df_f[df_f["promotion_status"] == sel_status]
    if sel_dir    != "All": df_f = df_f[df_f["direction"] == sel_dir]
 
    st.markdown(f"**{len(df_f):,} patterns** matching filters")
    st.markdown("---")
 
    col_s, col_t = st.columns([3, 2])
 
    # ── Scatter: WR vs PF ─────────────────────────────────────
    with col_s:
        st.markdown("### Win Rate vs Profit Factor")
        df_scatter = df_f[df_f["occurrences"] >= 20].copy()
        if not df_scatter.empty:
            df_scatter["win_rate_pct"] = df_scatter["win_rate"].apply(lambda v: v if v <= 1 else v/100)
            df_scatter["color"] = df_scatter["promotion_status"].map(promo_color).fillna("#94a3b8")
            fig = px.scatter(
                df_scatter,
                x="win_rate_pct", y="profit_factor",
                color="promotion_status",
                size="occurrences",
                size_max=20,
                hover_data=["symbol", "direction", "occurrences", "expectancy_r"],
                color_discrete_map={s: promo_color(s) for s in df_scatter["promotion_status"].unique()},
                template="plotly_dark",
            )
            fig.add_hline(y=1.0, line_dash="dash", line_color="#475569",
                          annotation_text="Breakeven PF=1.0")
            fig.add_vline(x=0.5, line_dash="dash", line_color="#475569",
                          annotation_text="WR=50%")
            fig.update_layout(
                paper_bgcolor="#0a0e1a", plot_bgcolor="#0f1629",
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis_title="Win Rate", yaxis_title="Profit Factor",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough patterns (need occurrences ≥ 20)")
 
    # ── Top 10 Edges ──────────────────────────────────────────
    with col_t:
        st.markdown("### Top 10 Edges by ExpR")
        validated_statuses = ["LIVE_APPROVED", "SHADOW_PASSED",
                               "RESEARCH_VALIDATED", "RESEARCH_DISCOVERED"]
        df_top = df_f[
            (df_f["promotion_status"].isin(validated_statuses)) &
            (df_f["occurrences"] >= 30)
        ].nlargest(10, "expectancy_r")[
            ["symbol", "direction", "promotion_status",
             "expectancy_r", "profit_factor", "win_rate", "occurrences"]
        ]
        if not df_top.empty:
            def fmt_wr(v):
                v = float(v)
                if v > 1: return f"{v:.1f}%"
                else: return f"{v:.1%}"
            df_top["win_rate"] = df_top["win_rate"].map(fmt_wr)
            df_top["profit_factor"] = df_top["profit_factor"].map("{:.2f}".format)
            df_top["expectancy_r"]  = df_top["expectancy_r"].map("{:.3f}".format)
            st.dataframe(df_top, use_container_width=True, hide_index=True)
        else:
            st.info("No validated patterns with N ≥ 30 in current filter")
 
    # ── Promotion status bar ──────────────────────────────────
    st.markdown("---")
    st.markdown("### Promotion Status by Symbol")
    if not df_f.empty:
        promo_sym = df_f.groupby(["symbol", "promotion_status"]).size().reset_index(name="count")
        fig = px.bar(
            promo_sym, x="symbol", y="count", color="promotion_status",
            color_discrete_map={s: promo_color(s) for s in promo_sym["promotion_status"].unique()},
            template="plotly_dark",
        )
        fig.update_layout(
            paper_bgcolor="#0a0e1a", plot_bgcolor="#0f1629",
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis_title="", yaxis_title="Pattern Count",
            legend_title="Status",
            legend=dict(
                font=dict(color="#94a3b8", size=10),
                bgcolor="rgba(0,0,0,0)",
                orientation="v",
                x=1.0,
                y=1.0,
                xanchor="left",
            )
        )
        st.plotly_chart(fig, use_container_width=True)
 
    # ── COT Institutional Bias ────────────────────────────────
    st.markdown("---")
    st.markdown("### 🏛️ Institutional Bias (COT Report - Hedge Funds)")
    try:
        from strategy.cot_analyzer import COTAnalyzer
        cot_rows = []
        for sym, name in COTAnalyzer.SYMBOL_MAP.items():
            pos = COTAnalyzer.get_net_position(sym)
            if pos:
                cot_rows.append({
                    "Symbol": sym,
                    "Net Position": pos['net_position'],
                    "Direction": pos['direction'],
                    "Longs": pos['longs'],
                    "Shorts": pos['shorts']
                })
        if cot_rows:
            df_cot = pd.DataFrame(cot_rows)
            df_cot = df_cot.sort_values("Net Position", ascending=False)
            df_cot["Net Position"] = df_cot["Net Position"].apply(lambda x: f"{x:,}")
            df_cot["Longs"] = df_cot["Longs"].apply(lambda x: f"{x:,}")
            df_cot["Shorts"] = df_cot["Shorts"].apply(lambda x: f"{x:,}")
            
            st.dataframe(
                df_cot.style.map(
                    lambda v: "color: #4ade80; font-weight: bold" if v == "BULLISH" else ("color: #f87171; font-weight: bold" if v == "BEARISH" else ""),
                    subset=["Direction"]
                ),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("COT Data unavailable or downloading.")
    except Exception as e:
        st.info("COT Analyzer not initialized.")

    # ── Full table ────────────────────────────────────────────
    with st.expander("📋 Full Pattern Table"):
        display_cols = ["pattern_id", "symbol", "direction", "promotion_status",
                        "profit_factor", "win_rate", "expectancy_r", "occurrences"]
        show_cols = [c for c in display_cols if c in df_f.columns]
        st.dataframe(df_f[show_cols].sort_values("expectancy_r", ascending=False),
                     use_container_width=True, hide_index=True)
 
# ══════════════════════════════════════════════════════════════
# PAGE 3 — LIVE OUTCOMES
# ══════════════════════════════════════════════════════════════
elif page == "📈 Live Outcomes":
    st.markdown("# 📈 Live Trading Outcomes")
 
    if df_out.empty:
        st.info("No live trades recorded yet.\n\nOutcomes will appear here once the bot completes trades.")
        st.stop()
 
    # ── Summary metrics ───────────────────────────────────────
    wins   = len(df_out[df_out["outcome"] == "WIN"])
    losses = len(df_out[df_out["outcome"] == "LOSS"])
    total  = len(df_out)
    wr     = wins / total * 100 if total > 0 else 0
    total_pnl = df_out["realized_pnl"].sum() if "realized_pnl" in df_out else 0
    avg_r  = df_out["actual_r"].dropna().mean() if "actual_r" in df_out else 0
    best   = df_out["realized_pnl"].max() if "realized_pnl" in df_out else 0
    worst  = df_out["realized_pnl"].min() if "realized_pnl" in df_out else 0
 
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("Total Trades", total)
    with c2: st.metric("Win Rate", f"{wr:.1f}%")
    with c3: st.metric("Total PnL", f"${total_pnl:+.2f}")
    with c4: st.metric("Best Trade", f"${best:+.2f}")
    with c5: st.metric("Worst Trade", f"${worst:+.2f}")
 
    st.markdown("---")
    col_l, col_r = st.columns(2)
 
    # ── Win Rate by Symbol ────────────────────────────────────
    with col_l:
        st.markdown("### Win Rate by Symbol")
        sym_stats = df_out.groupby("symbol").apply(
            lambda x: pd.Series({
                "trades": len(x),
                "win_rate": (x["outcome"] == "WIN").mean() * 100,
                "total_pnl": x["realized_pnl"].sum(),
            })
        ).reset_index()
        fig = px.bar(
            sym_stats.sort_values("win_rate", ascending=True),
            x="win_rate", y="symbol", orientation="h",
            color="win_rate",
            color_continuous_scale=[[0, "#f87171"], [0.5, "#facc15"], [1, "#4ade80"]],
            template="plotly_dark",
            text="win_rate",
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.add_vline(x=50, line_dash="dash", line_color="#475569")
        fig.update_layout(
            paper_bgcolor="#0a0e1a", plot_bgcolor="#0f1629",
            margin=dict(l=0, r=0, t=10, b=0),
            coloraxis_showscale=False,
            xaxis_title="Win Rate %", yaxis_title="",
        )
        st.plotly_chart(fig, use_container_width=True)
 
    # ── Similarity vs PnL ─────────────────────────────────────
    with col_r:
        st.markdown("### Pattern Similarity vs PnL")
        if "pattern_similarity" in df_out.columns and "realized_pnl" in df_out.columns:
            fig = px.scatter(
                df_out, x="pattern_similarity", y="realized_pnl",
                color="outcome",
                color_discrete_map={"WIN": "#4ade80", "LOSS": "#f87171", "TIMEOUT": "#facc15"},
                template="plotly_dark",
                hover_data=["symbol", "direction", "pattern_pf"],
            )
            fig.add_hline(y=0, line_color="#475569", line_dash="dash")
            fig.update_layout(
                paper_bgcolor="#0a0e1a", plot_bgcolor="#0f1629",
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis_title="Pattern Similarity", yaxis_title="Realized PnL ($)",
            )
            st.plotly_chart(fig, use_container_width=True)
 
    # ── Session breakdown ─────────────────────────────────────
    st.markdown("---")
    st.markdown("### Performance by Session")
    if "session" in df_out.columns:
        sess_stats = df_out.groupby("session").apply(
            lambda x: pd.Series({
                "trades":    len(x),
                "wins":      (x["outcome"] == "WIN").sum(),
                "losses":    (x["outcome"] == "LOSS").sum(),
                "win_rate":  (x["outcome"] == "WIN").mean() * 100,
                "total_pnl": x["realized_pnl"].sum(),
            })
        ).reset_index()
        st.dataframe(
            sess_stats.style.format({
                "trades":    "{:.0f}",
                "wins":      "{:.0f}",
                "losses":    "{:.0f}",
                "win_rate":  "{:.1f}%",
                "total_pnl": "${:+.2f}",
            }),
            use_container_width=True, hide_index=True,
        )
 
    # ── Slippage stats ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🧊 Slippage Analytics")
    df_slip = load_slippage()
    if not df_slip.empty:
        slip_stats = df_slip.groupby("symbol").apply(
            lambda x: pd.Series({
                "Trades": len(x),
                "Avg Slippage (Pips)": x["slippage_pips"].mean(),
                "Total Cost": x["slippage_usd"].sum(),
                "Avg Exec Time": x["execution_time_ms"].mean()
            })
        ).reset_index()
        st.dataframe(
            slip_stats.style.format({
                "Avg Slippage (Pips)": "{:.2f}",
                "Total Cost": "${:.2f}",
                "Avg Exec Time": "{:.0f} ms"
            }),
            use_container_width=True, hide_index=True
        )
    else:
        st.info("No slippage data recorded yet.")

    # ── Recent trades ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Recent Trades")
    show_cols = [c for c in ["close_time", "symbol", "direction", "outcome",
                              "realized_pnl", "actual_r", "pattern_id",
                              "pattern_pf", "session"]
                 if c in df_out.columns]
    df_recent = df_out.sort_values("close_time", ascending=False).head(20)[show_cols]
 
    def color_outcome(val):
        if val == "WIN":   return "color: #4ade80"
        if val == "LOSS":  return "color: #f87171"
        return "color: #facc15"
 
    def color_pnl(val):
        try:
            return "color: #4ade80" if float(val) > 0 else "color: #f87171"
        except Exception:
            return ""
 
    styled = df_recent.style
    if "outcome" in show_cols:
        styled = styled.map(color_outcome, subset=["outcome"])
    if "realized_pnl" in show_cols:
        styled = styled.map(color_pnl, subset=["realized_pnl"])
        styled = styled.format({"realized_pnl": "${:+.2f}", "actual_r": "{:.2f}R"})
 
    st.dataframe(styled, use_container_width=True, hide_index=True)
 
# ── Footer ─────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<small style='color:#334155'>GQOS TradePro • Pattern Promotion Dashboard • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</small>",
    unsafe_allow_html=True,
)
