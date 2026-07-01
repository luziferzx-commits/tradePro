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
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from streamlit_autorefresh import st_autorefresh
 
# ── Page config ────────────────────────────────────────────────
st.set_page_config(
    page_title="GQOS TradePro",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st_autorefresh(interval=60000, key="data_refresh")

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
PENDING_PATH    = "data/learning/pending_trades.json"
SLIPPAGE_PATH   = "data/learning/slippage_log.jsonl"
MISSED_PENDING_PATH = "data/learning/missed_opportunities.json"
MISSED_OUTCOMES_PATH = "data/learning/missed_opportunity_outcomes.jsonl"
VIRTUAL_PENDING_PATH = "data/learning/virtual_trades.json"
VIRTUAL_OUTCOMES_PATH = "data/learning/virtual_trade_outcomes.jsonl"
MARKET_OBS_PATH = "data/learning/market_observations.jsonl"
SIM_RECOMMENDATIONS_PATH = "data/learning/simulation_recommendations.json"


def parse_datetime_series(values):
    try:
        parsed = pd.to_datetime(values, errors="coerce", format="mixed", utc=True)
    except TypeError:
        parsed = pd.to_datetime(values, errors="coerce", utc=True)
    try:
        return parsed.dt.tz_convert(None)
    except AttributeError:
        return parsed

@st.cache_data(ttl=30)
def load_slippage():
    if not os.path.exists(SLIPPAGE_PATH):
        return pd.DataFrame()
    rows = []
    with open(SLIPPAGE_PATH, encoding="utf-8-sig") as f:
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
    with open(OUTCOMES_PATH, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "close_time" in df.columns:
        df["close_time"] = parse_datetime_series(df["close_time"])
    return df

@st.cache_data(ttl=10)
def load_pending_trades():
    if not os.path.exists(PENDING_PATH):
        return pd.DataFrame()
    try:
        with open(PENDING_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return pd.DataFrame()
    if not isinstance(data, dict) or not data:
        return pd.DataFrame()
    rows = []
    for decision_id, item in data.items():
        if isinstance(item, dict):
            row = item.copy()
            row.setdefault("decision_id", decision_id)
            rows.append(row)
    df = pd.DataFrame(rows)
    if "open_time" in df.columns:
        df["open_time"] = parse_datetime_series(df["open_time"])
    return df

@st.cache_data(ttl=10)
def load_retrain_state():
    path = os.getenv("GQOS_RETRAIN_STATE_PATH", "data/learning/retrain_state.json")
    threshold = int(os.getenv("GQOS_RETRAIN_THRESHOLD", "50"))
    if not os.path.exists(path):
        return {
            "trades_since_retrain": 0,
            "next_retrain_in": threshold,
            "threshold": threshold,
        }
    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}
    progress = int(state.get("trades_since_retrain", 0) or 0)
    state["threshold"] = threshold
    state["next_retrain_in"] = max(0, threshold - progress)
    return state

@st.cache_data(ttl=10)
def load_missed_opportunities():
    pending = {}
    if os.path.exists(MISSED_PENDING_PATH):
        try:
            with open(MISSED_PENDING_PATH, "r", encoding="utf-8") as f:
                pending = json.load(f)
        except Exception:
            pending = {}
    rows = []
    if os.path.exists(MISSED_OUTCOMES_PATH):
        with open(MISSED_OUTCOMES_PATH, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    df = pd.DataFrame(rows)
    if not df.empty and "close_time" in df.columns:
        df["close_time"] = parse_datetime_series(df["close_time"])
    return pending if isinstance(pending, dict) else {}, df

@st.cache_data(ttl=10)
def load_continuous_sim():
    pending = {}
    if os.path.exists(VIRTUAL_PENDING_PATH):
        try:
            with open(VIRTUAL_PENDING_PATH, "r", encoding="utf-8") as f:
                pending = json.load(f)
        except Exception:
            pending = {}
    rows = []
    if os.path.exists(VIRTUAL_OUTCOMES_PATH):
        with open(VIRTUAL_OUTCOMES_PATH, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    obs_count = 0
    if os.path.exists(MARKET_OBS_PATH):
        try:
            with open(MARKET_OBS_PATH, "r", encoding="utf-8", errors="ignore") as f:
                obs_count = sum(1 for line in f if line.strip())
        except Exception:
            obs_count = 0
    df = pd.DataFrame(rows)
    if not df.empty and "close_time" in df.columns:
        df["close_time"] = parse_datetime_series(df["close_time"])
    return pending if isinstance(pending, dict) else {}, df, obs_count

@st.cache_data(ttl=10)
def load_sim_recommendations():
    if not os.path.exists(SIM_RECOMMENDATIONS_PATH):
        return {}
    try:
        with open(SIM_RECOMMENDATIONS_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return {}, {}
        return payload.get("recommendations", {}), payload.get("context_recommendations", {})
    except Exception:
        return {}, {}

@st.cache_data(ttl=20)
def load_learning_insights():
    try:
        from gqos.ops.learning_insights import (
            build_learning_coverage,
            build_live_sim_agreement,
            build_session_scores,
            build_why_table,
        )
        return {
            "coverage": build_learning_coverage(),
            "agreement": build_live_sim_agreement(),
            "sessions": build_session_scores(),
            "why": build_why_table(),
        }
    except Exception as exc:
        return {"error": str(exc), "coverage": {}, "agreement": {}, "sessions": [], "why": []}

@st.cache_data(ttl=20)
def load_recovery_ops():
    try:
        from gqos.ops.recovery_readiness import build_recovery_readiness
        from gqos.ops.spread_regime_memory import spread_regime_summary
        return {
            "readiness": build_recovery_readiness(),
            "spread_memory": spread_regime_summary(),
        }
    except Exception as exc:
        return {"error": str(exc), "readiness": {}, "spread_memory": []}

@st.cache_data(ttl=30)
def load_post_trade_reviews():
    path = "data/learning/post_trade_reviews.jsonl"
    rows = []
    if not os.path.exists(path):
        return pd.DataFrame()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return pd.DataFrame(rows)

@st.cache_data(ttl=30)
def load_pa_filter_analytics():
    try:
        from gqos.ops.pa_filter_analytics import (
            build_pa_counterfactual_scores,
            build_pa_outcome_scores,
            build_pa_rejection_summary,
        )
        from gqos.ops.pa_filter_calibrator import build_pa_filter_scorecard
        return {
            "rejections": build_pa_rejection_summary(),
            "outcomes": build_pa_outcome_scores(),
            "counterfactual": build_pa_counterfactual_scores(),
            "scorecard": build_pa_filter_scorecard(),
        }
    except Exception as exc:
        return {"error": str(exc), "rejections": [], "outcomes": [], "counterfactual": [], "scorecard": []}

def build_live_trade_history(df_out, pos, df_pending):
    rows = []
    if not df_out.empty:
        closed = df_out.copy()
        closed["status"] = "CLOSED"
        rows.append(closed)

    pending_by_symbol = {}
    if not df_pending.empty and "symbol" in df_pending.columns:
        for _, row in df_pending.iterrows():
            pending_by_symbol.setdefault(str(row.get("symbol", "")), row)

    open_rows = []
    for p in pos or []:
        side = "BUY" if p.type == 0 else "SELL"
        meta = pending_by_symbol.get(p.symbol)
        open_rows.append({
            "status": "OPEN",
            "symbol": p.symbol,
            "direction": side,
            "entry_price": p.price_open,
            "sl_price": p.sl,
            "tp_price": p.tp,
            "pattern_id": "" if meta is None else meta.get("pattern_id", ""),
            "pattern_pf": None if meta is None else meta.get("pattern_pf"),
            "pattern_similarity": None if meta is None else meta.get("pattern_similarity"),
            "session": "" if meta is None else meta.get("session", ""),
            "strategy_id": "" if meta is None else meta.get("strategy_id", ""),
            "decision_id": "" if meta is None else meta.get("decision_id", ""),
            "open_time": getattr(p, "time", None),
            "ticket": p.ticket,
            "close_price": None,
            "realized_pnl": None,
            "floating_pnl": p.profit,
            "actual_r": None,
            "outcome": "OPEN",
            "close_time": None,
        })
    if open_rows:
        rows.append(pd.DataFrame(open_rows))

    if not rows:
        return pd.DataFrame()
    df = pd.concat(rows, ignore_index=True, sort=False)
    if "open_time" in df.columns:
        numeric_mask = pd.to_numeric(df["open_time"], errors="coerce").notna()
        if numeric_mask.any():
            df.loc[numeric_mask, "open_time"] = pd.to_datetime(
                pd.to_numeric(df.loc[numeric_mask, "open_time"], errors="coerce"),
                unit="s",
                errors="coerce",
            )
        df["open_time"] = parse_datetime_series(df["open_time"])
    if "close_time" in df.columns:
        df["close_time"] = parse_datetime_series(df["close_time"])
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

@st.cache_data(ttl=10)
def load_mt5_closed_deals_today():
    try:
        import MetaTrader5 as mt5
        from config.settings import settings
        from execution.mt5_direction import closing_deal_position_direction

        if not mt5.terminal_info():
            mt5.initialize(
                login=settings.MT5_LOGIN,
                password=settings.MT5_PASSWORD,
                server=settings.MT5_SERVER,
            )

        guard_tz = ZoneInfo(getattr(settings, "DAILY_GUARD_TIMEZONE", "Asia/Bangkok"))
        now_local = datetime.now(guard_tz)
        start_utc = now_local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
        end_utc = now_local.astimezone(timezone.utc).replace(tzinfo=None)
        deals = mt5.history_deals_get(start_utc, end_utc) or []

        rows = []
        for d in deals:
            if getattr(d, "entry", None) != mt5.DEAL_ENTRY_OUT:
                continue
            profit = float(getattr(d, "profit", 0.0))
            if profit == 0.0:
                continue
            rows.append({
                "status": "CLOSED",
                "symbol": d.symbol,
                "direction": closing_deal_position_direction(d.type),
                "entry_price": None,
                "sl_price": None,
                "tp_price": None,
                "pattern_id": "",
                "pattern_pf": None,
                "pattern_similarity": None,
                "session": "MT5_HISTORY",
                "strategy_id": "mt5_history",
                "decision_id": f"MT5-{getattr(d, 'position_id', getattr(d, 'ticket', ''))}",
                "open_time": None,
                "ticket": getattr(d, "position_id", getattr(d, "ticket", "")),
                "deal_ticket": getattr(d, "ticket", ""),
                "floating_pnl": None,
                "close_price": getattr(d, "price", None),
                "realized_pnl": profit,
                "actual_r": None,
                "outcome": "WIN" if profit > 0 else "LOSS",
                "close_time": datetime.fromtimestamp(d.time, guard_tz),
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()
 
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

def merge_closed_trades(df_out, df_mt5_closed):
    frames = []
    if not df_out.empty:
        closed = df_out.copy()
        closed["status"] = closed.get("status", "CLOSED")
        frames.append(closed)
    if not df_mt5_closed.empty:
        frames.append(df_mt5_closed.copy())
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True, sort=False)
    if "ticket" in df.columns:
        df["_ticket_key"] = df["ticket"].astype(str)
        df = df.drop_duplicates("_ticket_key", keep="first").drop(columns=["_ticket_key"])
    if "close_time" in df.columns:
        df["close_time"] = parse_datetime_series(df["close_time"])
    return df
 
# ── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 GQOS TradePro")
    st.markdown("---")
    page = st.radio(
        "Navigation",
        ["📊 Overview", "🚫 Rejection Analytics", "🧠 Pattern Knowledge Base", "📈 Live Outcomes", "❤️ Edge Health"],
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
df_pending = load_pending_trades()
df_mt5_closed = load_mt5_closed_deals_today()
df_closed = merge_closed_trades(df_out, df_mt5_closed)
 
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
        retrain_state = load_retrain_state()
        progress = int(retrain_state.get("trades_since_retrain", 0) or 0)
        threshold = int(retrain_state.get("threshold", 50) or 50)
        next_retrain = int(retrain_state.get("next_retrain_in", max(0, threshold - progress)) or 0)
        st.metric(
            "Retrain Progress",
            f"{progress} / {threshold}",
            delta=f"{next_retrain} trades until next retrain",
            delta_color="off",
        )
        
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
    col_a, col_b, col_c, col_d, col_e = st.columns(5)
    if not df_closed.empty:
        wins   = len(df_closed[df_closed["outcome"] == "WIN"])
        losses = len(df_closed[df_closed["outcome"] == "LOSS"])
        total  = len(df_closed)
        wr     = wins / total * 100 if total > 0 else 0
        total_pnl = df_closed["realized_pnl"].sum() if "realized_pnl" in df_closed else 0
        avg_r  = df_closed["actual_r"].dropna().mean() if "actual_r" in df_closed else 0
        pattern_count = df_closed["pattern_id"].fillna("").astype(str).str.len().gt(0).sum() if "pattern_id" in df_closed else 0
        learning_quality = pattern_count / total * 100 if total else 0
 
        with col_a: st.metric("Live Trades", total)
        with col_b: st.metric("Win Rate", f"{wr:.1f}%",
                              delta=f"{wins}W {losses}L")
        with col_c: st.metric("Total PnL", f"${total_pnl:+.2f}")
        with col_d: st.metric("Avg R", f"{avg_r:.2f}R")
        with col_e: st.metric("Learning Quality", f"{learning_quality:.0f}%", delta=f"{pattern_count}/{total} tagged")
    else:
        with col_a: st.metric("Live Trades", 0)
        with col_b: st.metric("Win Rate", "—")
        with col_c: st.metric("Total PnL", "$0.00")
        with col_d: st.metric("Avg R", "—")
 
    st.markdown("---")
    missed_pending, missed_df = load_missed_opportunities()
    sim_pending, sim_df, sim_obs_count = load_continuous_sim()
    sim_recs, sim_context_recs = load_sim_recommendations()
    sim_total = len(sim_df)
    sim_wins = 0
    sim_wr = 0.0
    sim_avg_r = 0.0
    if sim_total:
        outcomes_str = sim_df["outcome"].fillna("").astype(str) if "outcome" in sim_df.columns else pd.Series([], dtype=str)
        sim_wins = outcomes_str.str.startswith("WIN").sum() + outcomes_str.str.startswith("TIMEOUT_WIN").sum()
        sim_wr = sim_wins / sim_total * 100
        sim_avg_r = sim_df["actual_r"].fillna(0).astype(float).mean() if "actual_r" in sim_df.columns else 0.0

    s1, s2, s3, s4 = st.columns(4)
    with s1: st.metric("M1 Observations", sim_obs_count)
    with s2: st.metric("Virtual Open", len(sim_pending) if isinstance(sim_pending, dict) else 0)
    with s3: st.metric("Virtual Closed", sim_total, delta=f"{sim_wr:.1f}% would-win")
    with s4: st.metric("Virtual Avg R", f"{sim_avg_r:+.2f}R", delta=f"{len(sim_recs)} sim recs")

    if sim_context_recs:
        all_context_rows = list(sim_context_recs.values())
        for row in all_context_rows:
            if not row.get("soft_rule"):
                action = str(row.get("action") or "NEUTRAL")
                row["soft_rule"] = "WATCH_POSITIVE" if action == "RELAX_SLIGHTLY" else ("WATCH_NEGATIVE" if action == "TIGHTEN_SLIGHTLY" else "NEUTRAL")
            if row.get("confidence") is None:
                try:
                    row["confidence"] = min(1.0, int(row.get("samples", 0) or 0) / max(20 * 3, 1))
                except Exception:
                    row["confidence"] = 0.0
            row.setdefault("stability", 0.0)
            row.setdefault("effective_samples", row.get("samples", 0))
        context_rows = [
            row for row in all_context_rows
            if any(
                str(row.get(field) or "UNKNOWN").upper() != "UNKNOWN"
                for field in ("session", "market_session", "spread_bucket", "volatility_bucket")
            )
        ] or all_context_rows
        top_rows = sorted(
            [
                row for row in context_rows
                if str(row.get("soft_rule", "")).endswith("WHITELIST") or float(row.get("avg_r", 0.0) or 0.0) > 0
            ],
            key=lambda row: (
                float(row.get("avg_r", 0.0) or 0.0),
                float(row.get("confidence", 0.0) or 0.0),
                int(row.get("samples", 0) or 0),
            ),
            reverse=True,
        )[:8]
        bottom_rows = sorted(
            [
                row for row in context_rows
                if str(row.get("soft_rule", "")).endswith("BLACKLIST") or float(row.get("avg_r", 0.0) or 0.0) < 0
            ],
            key=lambda row: (
                float(row.get("avg_r", 0.0) or 0.0),
                -float(row.get("confidence", 0.0) or 0.0),
                -int(row.get("samples", 0) or 0),
            ),
        )[:8]
        display_cols = [
            "symbol", "side", "session", "market_session", "spread_bucket", "volatility_bucket",
            "samples", "effective_samples", "win_rate", "avg_r", "confidence", "stability", "soft_rule", "action",
        ]
        st.markdown("### Simulation Context Recommendations")
        col_top, col_bad = st.columns(2)
        with col_top:
            st.markdown("#### Top Contexts")
            if top_rows:
                df_top_ctx = pd.DataFrame(top_rows)
                st.dataframe(df_top_ctx[[c for c in display_cols if c in df_top_ctx.columns]], use_container_width=True, hide_index=True)
            else:
                st.caption("No positive simulation contexts qualified yet.")
        with col_bad:
            st.markdown("#### Bottom Contexts")
            if bottom_rows:
                df_bad_ctx = pd.DataFrame(bottom_rows)
                st.dataframe(df_bad_ctx[[c for c in display_cols if c in df_bad_ctx.columns]], use_container_width=True, hide_index=True)
            else:
                st.caption("No negative simulation contexts qualified yet.")

    insights = load_learning_insights()
    agreement = insights.get("agreement", {})
    coverage = insights.get("coverage", {})
    sessions = insights.get("sessions", [])
    st.markdown("### Live vs Simulation Agreement")
    a1, a2, a3, a4, a5 = st.columns(5)
    with a1: st.metric("Agreement", f"{float(agreement.get('agreement_rate', 0.0)):.0f}%")
    with a2: st.metric("Agree", int(agreement.get("agree", 0) or 0))
    with a3: st.metric("Disagree", int(agreement.get("disagree", 0) or 0))
    with a4: st.metric("Neutral", int(agreement.get("neutral", 0) or 0))
    with a5: st.metric("New Tagged Quality", f"{float(coverage.get('new_quality', 0.0)):.0f}%", delta=f"{coverage.get('new_tagged', 0)}/{coverage.get('new_total', 0)}")
    if agreement.get("rows"):
        agree_df = pd.DataFrame(agreement["rows"])
        st.dataframe(
            agree_df.tail(12)[[
                c for c in [
                    "symbol", "side", "outcome", "actual_r", "sim_action", "soft_rule",
                    "sim_confidence", "sim_avg_r", "verdict",
                ] if c in agree_df.columns
            ]],
            use_container_width=True,
            hide_index=True,
        )
    if agreement.get("context_rows"):
        ctx_agree_df = pd.DataFrame(agreement["context_rows"])
        st.markdown("#### Context-Level Agreement")
        st.dataframe(
            ctx_agree_df[["symbol", "side", "session", "samples", "agreement_rate", "agree", "disagree", "neutral"]].head(12),
            use_container_width=True,
            hide_index=True,
        )

    recovery_ops = load_recovery_ops()
    readiness = recovery_ops.get("readiness", {})
    st.markdown("### Recovery Readiness")
    r1, r2, r3, r4, r5 = st.columns(5)
    with r1: st.metric("Readiness", f"{float(readiness.get('score', 0.0)):.0%}")
    with r2: st.metric("Tier", readiness.get("tier", "NA"))
    with r3: st.metric("Probe Multiplier", f"{float(readiness.get('probe_multiplier', 0.0)):.2f}x")
    with r4: st.metric("Spread OK", f"{readiness.get('spread_ok', 0)}/{readiness.get('symbols', 0)}")
    with r5: st.metric("Paused Symbols", readiness.get("portfolio_paused", 0))

    spread_memory = recovery_ops.get("spread_memory", [])
    if spread_memory:
        st.markdown("#### Spread Regime Memory")
        spread_df = pd.DataFrame(spread_memory)
        st.dataframe(
            spread_df[["symbol", "session", "samples", "blocked", "block_rate", "avg_spread_ratio", "label"]].head(12),
            use_container_width=True,
            hide_index=True,
        )

    reviews_df = load_post_trade_reviews()
    if not reviews_df.empty:
        st.markdown("### Post-Trade Reviews")
        review_cols = [
            "ts", "symbol", "direction", "session", "entry_mode", "outcome", "actual_r",
            "simulation_soft_rule", "simulation_confidence", "pa_h4_trend", "pa_h4_divergence",
            "pa_liquidity_sweep", "pa_fvg_aligned", "pa_killzone", "review_verdict",
        ]
        st.dataframe(
            reviews_df.tail(12)[[c for c in review_cols if c in reviews_df.columns]],
            use_container_width=True,
            hide_index=True,
        )

    pa = load_pa_filter_analytics()
    st.markdown("### Price Action Filter Analytics")
    pa_cols = st.columns(3)
    with pa_cols[0]:
        st.markdown("#### Filter Pressure")
        if pa.get("rejections"):
            st.dataframe(pd.DataFrame(pa["rejections"]).head(8), use_container_width=True, hide_index=True)
        else:
            st.caption("No PA-specific rejections yet.")
    with pa_cols[1]:
        st.markdown("#### Live Outcome Score")
        if pa.get("outcomes"):
            st.dataframe(pd.DataFrame(pa["outcomes"]).head(8), use_container_width=True, hide_index=True)
        else:
            st.caption("No closed trades with PA tags yet.")
    with pa_cols[2]:
        st.markdown("#### Counterfactual")
        if pa.get("counterfactual"):
            st.dataframe(pd.DataFrame(pa["counterfactual"]).head(8), use_container_width=True, hide_index=True)
        else:
            st.caption("Waiting for missed-opportunity outcomes.")
    st.markdown("#### Auto-Calibration Scorecard")
    if pa.get("scorecard"):
        score_cols = [
            "category", "recommended_action", "confidence", "reason", "rejections",
            "live_samples", "live_win_rate", "live_avg_r",
            "counterfactual_samples", "counterfactual_win_rate", "counterfactual_avg_r",
        ]
        score_df = pd.DataFrame(pa["scorecard"])
        st.dataframe(score_df[[c for c in score_cols if c in score_df.columns]].head(12), use_container_width=True, hide_index=True)
    else:
        st.caption("PA calibration scorecard is waiting for more data.")

    st.markdown("### Session Scores")
    if sessions:
        sess_df = pd.DataFrame(sessions)
        st.dataframe(
            sess_df[["symbol", "side", "session", "samples", "win_rate", "avg_r", "pnl", "score", "label"]].head(12),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("Need more live outcomes per session before scoring.")

    st.markdown("---")
    col_left, col_right = st.columns([2, 1])
 
    # ── PnL Curve ─────────────────────────────────────────────
    with col_left:
        st.markdown("### Cumulative PnL")
        if not df_closed.empty and "realized_pnl" in df_closed.columns:
            df_curve = df_closed.sort_values("close_time").copy()
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
 
    # ── PnL by Symbol ─────────────────────────────────────────
    if not df_closed.empty and "realized_pnl" in df_closed.columns and "symbol" in df_closed.columns:
        st.markdown("### PnL by Symbol")
        df_sym = df_closed.groupby("symbol")["realized_pnl"].sum().reset_index()
        df_sym = df_sym.sort_values("realized_pnl", ascending=True) # Ascending for horizontal bar, or False for vertical
        fig_sym = px.bar(
            df_sym, x="symbol", y="realized_pnl",
            color="realized_pnl",
            color_continuous_scale=["#f87171", "#1e293b", "#4ade80"],
            color_continuous_midpoint=0,
            template="plotly_dark",
            text="realized_pnl"
        )
        fig_sym.update_traces(texttemplate='%{text:$.2f}', textposition='outside')
        fig_sym.update_layout(
            paper_bgcolor="#0a0e1a", plot_bgcolor="#0f1629",
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis_title="", yaxis_title="USD PnL",
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_sym, use_container_width=True)

    # ── Trade History ─────────────────────────────────────────
    df_trade_history = build_live_trade_history(df_closed, pos, df_pending)
    if not df_trade_history.empty:
        st.markdown("### Trade History")
        sort_col = "close_time" if "close_time" in df_trade_history.columns else "open_time"
        display_cols = [
            "status", "symbol", "direction", "entry_price", "sl_price", "tp_price",
            "pattern_id", "pattern_pf", "pattern_similarity", "session",
            "strategy_id", "decision_id", "open_time", "ticket",
            "floating_pnl", "close_price", "realized_pnl", "actual_r", "outcome", "close_time",
        ]
        display_cols = [c for c in display_cols if c in df_trade_history.columns]
        st.dataframe(
            df_trade_history.sort_values(sort_col, ascending=False, na_position="first")[display_cols].style.map(
                lambda v: "color: #4ade80" if isinstance(v, str) and v in {"WIN", "OPEN"}
                else ("color: #f87171" if isinstance(v, str) and v == "LOSS" else ""),
                subset=["outcome"]
            ),
            use_container_width=True, hide_index=True
        )
# ══════════════════════════════════════════════════════════════
# PAGE 1.5 — REJECTION ANALYTICS
# ══════════════════════════════════════════════════════════════
elif page == "🚫 Rejection Analytics":
    st.markdown("# 🚫 Trade Rejection Analytics")
    st.markdown("Understand why the system rejected or skipped signals.")
    
    events_file = os.path.join(os.path.abspath("data"), "learning", "system_events.jsonl")
    
    if not os.path.exists(events_file):
        st.info("No system events found yet. The live bot needs to run and scan markets.")
    else:
        events = []
        try:
            with open(events_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            events.append(json.loads(line))
                        except Exception:
                            pass
        except Exception as e:
            st.error(f"Failed to read events: {e}")
            
        if events:
            df_events = pd.DataFrame(events)
            df_events['ts'] = parse_datetime_series(df_events['ts'])
            
            # Today's Summary
            today = datetime.utcnow().date()
            df_today = df_events[df_events['ts'].dt.date == today]
            
            st.markdown("### 📅 Today's Summary")
            
            # Counts (Using unique decision_id to prevent double counting)
            total_evaluated = df_today[df_today['event_type'] == 'SIGNAL_EVALUATED']['decision_id'].nunique() if 'decision_id' in df_today.columns else 0
            total_rejected = df_today[df_today['event_type'] == 'SIGNAL_REJECTED']['decision_id'].nunique() if 'decision_id' in df_today.columns else 0
            total_skipped = df_today[df_today['event_type'] == 'SIGNAL_SKIPPED']['decision_id'].nunique() if 'decision_id' in df_today.columns else 0
            total_approved = df_today[df_today['event_type'] == 'SIGNAL_APPROVED']['decision_id'].nunique() if 'decision_id' in df_today.columns else 0
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Signals Evaluated", total_evaluated)
            col2.metric("Approved", total_approved)
            col3.metric("Skipped (State/Risk)", total_skipped)
            col4.metric("Rejected (Edge)", total_rejected)

            insights = load_learning_insights()
            why_rows = insights.get("why", [])
            st.markdown("### Why Blocked / Why Allowed")
            if why_rows:
                why_df = pd.DataFrame(why_rows)
                why_cols = [
                    "symbol", "side", "status", "reason", "pf", "expectancy_r", "similarity",
                    "sim_action", "soft_rule", "sim_confidence", "sim_avg_r", "ts",
                ]
                st.dataframe(
                    why_df[[c for c in why_cols if c in why_df.columns]].sort_values("ts", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No recent decision reasons available yet.")
            
            st.markdown("---")
            
            # Reasons Bar Chart
            st.markdown("### 📊 Rejection & Skipping Reasons")
            reasons = df_today[df_today['event_type'].isin(['SIGNAL_REJECTED', 'SIGNAL_SKIPPED'])]
            if not reasons.empty:
                # Clean up reason strings
                reasons['reason_clean'] = reasons['reason'].apply(lambda x: x.split('(')[0].strip() if isinstance(x, str) else x)
                reason_counts = reasons.groupby(['reason_clean', 'event_type']).size().reset_index(name='count')
                
                fig = px.bar(
                    reason_counts, 
                    x='count', 
                    y='reason_clean', 
                    color='event_type',
                    orientation='h',
                    color_discrete_map={'SIGNAL_REJECTED': '#f87171', 'SIGNAL_SKIPPED': '#facc15'},
                    title="Reasons for Non-Execution"
                )
                fig.update_layout(template="plotly_dark", yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No rejections or skips today.")
                
            st.markdown("---")
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                # Top Reject Symbol & Reject Rate
                st.markdown("### 🚫 Reject Rate by Symbol")
                evals = df_today[df_today['event_type'] == 'SIGNAL_EVALUATED'].groupby('symbol')['decision_id'].nunique().reset_index(name='Evaluated')
                rejects = df_today[df_today['event_type'] == 'SIGNAL_REJECTED'].groupby('symbol')['decision_id'].nunique().reset_index(name='Rejected')
                
                if not evals.empty:
                    df_rate = pd.merge(evals, rejects, on='symbol', how='left').fillna(0)
                    df_rate['Reject Rate'] = (df_rate['Rejected'] / df_rate['Evaluated']) * 100
                    df_rate['Reject Rate'] = df_rate['Reject Rate'].clip(upper=100)
                    df_rate = df_rate.sort_values('Rejected', ascending=False)
                    
                    df_rate['Reject Rate'] = df_rate['Reject Rate'].apply(lambda x: f"{x:.1f}%")
                    st.dataframe(df_rate, use_container_width=True, hide_index=True)
                else:
                    st.info("No evaluated signals yet.")
                    
            with col_b:
                # Near Miss Analytics
                st.markdown("### 🎯 Profit Factor 'Near Miss' Analytics")
                rejects_pf = df_today[(df_today['event_type'] == 'SIGNAL_REJECTED') & (df_today['reason'].str.contains("Profit Factor Low", na=False))]
                
                if not rejects_pf.empty:
                    def classify_miss(pf):
                        if pf >= 1.05: return "Near Miss (1.05-1.09)"
                        if pf >= 1.00: return "Miss (1.00-1.04)"
                        return "Critical Miss (<1.00)"
                    
                    miss_data = []
                    for _, row in rejects_pf.iterrows():
                        # Due to payload flattening in structured_logger, profit_factor might be a direct column
                        pf = None
                        if 'profit_factor' in row and pd.notna(row['profit_factor']):
                            pf = row['profit_factor']
                        else:
                            md = row.get('metadata', {})
                            if isinstance(md, dict) and 'profit_factor' in md:
                                pf = md['profit_factor']
                                
                        if pf is not None:
                            miss_data.append(classify_miss(pf))
                            
                    if miss_data:
                        df_miss = pd.DataFrame(miss_data, columns=['Category']).value_counts().reset_index(name='Count')
                        # Ensure specific order
                        order = ["Near Miss (1.05-1.09)", "Miss (1.00-1.04)", "Critical Miss (<1.00)"]
                        df_miss['Category'] = pd.Categorical(df_miss['Category'], categories=order, ordered=True)
                        df_miss = df_miss.sort_values('Category')
                        
                        fig_miss = px.bar(
                            df_miss,
                            x='Category',
                            y='Count',
                            color='Category',
                            color_discrete_map={
                                "Near Miss (1.05-1.09)": "#facc15",  # Yellow
                                "Miss (1.00-1.04)": "#fb923c",       # Orange
                                "Critical Miss (<1.00)": "#ef4444"   # Red
                            },
                            title="Profit Factor Rejections Distribution"
                        )
                        fig_miss.update_layout(template="plotly_dark", showlegend=False)
                        st.plotly_chart(fig_miss, use_container_width=True)
                    else:
                        st.info("No Profit Factor data found in metadata.")
                else:
                    st.info("No Profit Factor rejections today.")
                    
            st.markdown("---")
            
            # 🌪️ Pipeline Funnel
            st.markdown("### 🌪️ Evaluation Pipeline Funnel")
            
            funnel_scanned = total_evaluated
            
            # Count rejections by category
            fail_sim = df_today[(df_today['event_type'] == 'SIGNAL_REJECTED') & (df_today['reason'].str.contains("Similarity", na=False))].shape[0]
            fail_n = df_today[(df_today['event_type'] == 'SIGNAL_REJECTED') & (df_today['reason'].str.contains("Sample Size", na=False))].shape[0]
            fail_pf = df_today[(df_today['event_type'] == 'SIGNAL_REJECTED') & (df_today['reason'].str.contains("Profit Factor", na=False))].shape[0]
            fail_expr = df_today[(df_today['event_type'] == 'SIGNAL_REJECTED') & (df_today['reason'].str.contains("Expectancy R", na=False))].shape[0]
            fail_promo = df_today[(df_today['event_type'] == 'SIGNAL_REJECTED') & (df_today['reason'].str.contains("Promotion", na=False))].shape[0]
            
            pass_sim = funnel_scanned - fail_sim
            pass_n = pass_sim - fail_n
            pass_pf = pass_n - fail_pf
            pass_expr = pass_pf - fail_expr
            pass_promo = pass_expr - fail_promo
            pass_risk = pass_promo - total_skipped
            
            funnel_data = dict(
                number=[funnel_scanned, pass_sim, pass_n, pass_pf, pass_expr, pass_promo, total_approved],
                stage=["1. Scanned", "2. Similarity Pass", "3. Sample Size Pass", "4. Profit Factor Pass", "5. ExpR Pass", "6. Promotion Pass", "7. Executed (Approved)"]
            )
            
            # Handle edge cases where previous counts are somehow negative due to missing EVALUATED logs from old data
            funnel_data['number'] = [max(0, n) for n in funnel_data['number']]
            
            fig_funnel = px.funnel(funnel_data, x='number', y='stage')
            fig_funnel.update_layout(template="plotly_dark")
            st.plotly_chart(fig_funnel, use_container_width=True)
            
            st.markdown("---")
            
            # Detailed Decision Tree Table
            st.markdown("### 🌳 Recent Decisions")
            recent = df_events[df_events['event_type'].isin(['SIGNAL_REJECTED', 'SIGNAL_SKIPPED', 'SIGNAL_APPROVED'])].tail(100).sort_values('ts', ascending=False)
            
            if not recent.empty:
                display_data = []
                for _, row in recent.iterrows():
                    sym = row.get('symbol', 'N/A')
                    side = row.get('side', 'N/A')
                    status = row.get('status', 'N/A')
                    reason = row.get('reason', 'N/A')
                    
                    dt = row.get('decision_tree', [])
                    if not dt and 'metadata' in row and isinstance(row['metadata'], dict):
                        dt = row['metadata'].get('decision_tree', [])
                        
                    dt_str = " → ".join(dt) if isinstance(dt, list) else str(dt)
                    
                    display_data.append({
                        "Time": row['ts'].strftime("%H:%M:%S"),
                        "Symbol": sym,
                        "Side": side,
                        "Status": "❌ REJECT" if status == "REJECTED" else ("⚠️ SKIP" if status == "SKIPPED" else "✅ PASS"),
                        "Reason": reason,
                        "Decision Tree": dt_str
                    })
                    
                df_disp = pd.DataFrame(display_data)
                
                def color_status(val):
                    color = '#4ade80' if 'PASS' in val else ('#f87171' if 'REJECT' in val else '#facc15')
                    return f'color: {color}'
                    
                st.dataframe(
                    df_disp.style.map(color_status, subset=['Status']), 
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.info("No decisions to display.")

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
    tagged = df_out["pattern_id"].fillna("").astype(str).str.len().gt(0).sum() if "pattern_id" in df_out else 0
    quality = tagged / total * 100 if total else 0
    probes = df_out["entry_mode"].fillna("NORMAL").ne("NORMAL").sum() if "entry_mode" in df_out else 0
 
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: st.metric("Total Trades", total)
    with c2: st.metric("Win Rate", f"{wr:.1f}%")
    with c3: st.metric("Total PnL", f"${total_pnl:+.2f}")
    with c4: st.metric("Best Trade", f"${best:+.2f}")
    with c5: st.metric("Worst Trade", f"${worst:+.2f}")
    with c6: st.metric("Learning Quality", f"{quality:.0f}%", delta=f"{tagged}/{total} tagged | {probes} probe")
 
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
                              "pattern_pf", "session", "entry_mode", "probe_reason"]
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
 
# ══════════════════════════════════════════════════════════════
# PAGE 4 — EDGE HEALTH
# ══════════════════════════════════════════════════════════════
elif page == "❤️ Edge Health":
    st.markdown("# ❤️ System Edge Health")
    from gqos.learning.edge_metrics import grouped_edge, rolling_edge

    st.markdown("### Rolling Edge Monitor")
    if df_out.empty:
        st.info("No clean live outcomes yet.")
    else:
        roll = rolling_edge(df_out, windows=(20, 50, 100))
        if not roll.empty:
            st.dataframe(
                roll.style.format({
                    "win_rate": "{:.1f}%",
                    "profit_factor": "{:.2f}",
                    "expectancy": "${:+.2f}",
                    "avg_r": "{:+.2f}R",
                    "total_pnl": "${:+.2f}",
                }),
                use_container_width=True,
                hide_index=True,
            )

        g1, g2 = st.columns(2)
        for col, group_col, title in [
            (g1, "symbol", "By Symbol"),
            (g2, "session", "By Session"),
        ]:
            with col:
                st.markdown(f"#### {title}")
                grouped = grouped_edge(df_out, group_col=group_col, window=50, min_trades=2)
                if grouped.empty:
                    st.caption("Waiting for more closed trades.")
                else:
                    st.dataframe(
                        grouped.head(10).style.format({
                            "win_rate": "{:.1f}%",
                            "profit_factor": "{:.2f}",
                            "expectancy": "${:+.2f}",
                            "avg_r": "{:+.2f}R",
                            "total_pnl": "${:+.2f}",
                        }),
                        use_container_width=True,
                        hide_index=True,
                    )

        g3, g4 = st.columns(2)
        for col, group_col, title in [
            (g3, "direction", "By Side"),
            (g4, "pattern_id", "By Pattern"),
        ]:
            with col:
                st.markdown(f"#### {title}")
                grouped = grouped_edge(df_out, group_col=group_col, window=50, min_trades=2)
                if grouped.empty:
                    st.caption("Waiting for more closed trades.")
                else:
                    st.dataframe(
                        grouped.head(10).style.format({
                            "win_rate": "{:.1f}%",
                            "profit_factor": "{:.2f}",
                            "expectancy": "${:+.2f}",
                            "avg_r": "{:+.2f}R",
                            "total_pnl": "${:+.2f}",
                        }),
                        use_container_width=True,
                        hide_index=True,
                    )

    st.markdown("---")
    
    import importlib
    import sys
    
    # Force reload the module to bypass Streamlit cache during development
    if "gqos.dashboard.edge_health" in sys.modules:
        importlib.reload(sys.modules["gqos.dashboard.edge_health"])
        
    from gqos.dashboard.edge_health import (
        calc_alpha_health, calc_execution_health, calc_risk_health,
        calc_learning_health, calc_overall_edge_health
    )
    
    df_slip = load_slippage()
    acc, pos = load_mt5_positions()
    
    # Calculate historical datasets (excluding last 24h) for trend calculation
    cutoff_time = datetime.now() - timedelta(days=1)
    
    if not df_out.empty and "close_time" in df_out.columns:
        df_out_hist = df_out[df_out["close_time"] < cutoff_time]
    else:
        df_out_hist = pd.DataFrame()
        
    if not df_slip.empty and "timestamp" in df_slip.columns:
        # Assuming slippage has a timestamp column, if not just don't calculate trend
        try:
            df_slip["timestamp"] = parse_datetime_series(df_slip["timestamp"])
            df_slip_hist = df_slip[df_slip["timestamp"] < cutoff_time]
        except Exception:
            df_slip_hist = pd.DataFrame()
    else:
        df_slip_hist = pd.DataFrame()
    
    # Current health
    alpha_h = calc_alpha_health(df_out)
    exec_h = calc_execution_health(df_slip)
    risk_h = calc_risk_health(acc, pos)
    learn_h = calc_learning_health(df_pat, df_out)
    
    # Historical health
    alpha_h_old = calc_alpha_health(df_out_hist)
    exec_h_old = calc_execution_health(df_slip_hist)
    # Risk and learning historical mocks (since we don't have historical state for MT5 or Pattern DB easily)
    
    # Set trends
    if alpha_h["score"] is not None and alpha_h_old["score"] is not None:
        alpha_h["trend"] = alpha_h["score"] - alpha_h_old["score"]
    if exec_h["score"] is not None and exec_h_old["score"] is not None:
        exec_h["trend"] = exec_h["score"] - exec_h_old["score"]
        
    overall_h = calc_overall_edge_health(alpha_h, exec_h, risk_h, learn_h)
    
    def status_color(status):
        if status == "HEALTHY": return "#4ade80"
        if status == "WATCH": return "#facc15"
        if status == "DEGRADED": return "#f97316"
        if status == "CRITICAL": return "#f87171"
        return "#94a3b8" # WARMING_UP
        
    # --- System Status Banner ---
    st.markdown("---")
    banner_color = status_color(overall_h["status"])
    banner_icon = "🟢" if overall_h["status"] == "HEALTHY" else ("🟡" if overall_h["status"] == "WATCH" else "🔴")
    if overall_h["status"] == "WARMING_UP": banner_icon = "⚪"
    
    # Find the worst dimension for the banner reason
    dim_statuses = [
        ("Alpha", alpha_h["status"]), 
        ("Execution", exec_h["status"]), 
        ("Risk", risk_h["status"]), 
        ("Learning", learn_h["status"])
    ]
    
    criticals = [d for d in dim_statuses if d[1] == "CRITICAL"]
    degradeds = [d for d in dim_statuses if d[1] == "DEGRADED"]
    watches = [d for d in dim_statuses if d[1] == "WATCH"]
    
    banner_msg = "System operating normally"
    if criticals:
        banner_msg = f"{criticals[0][0]} Critical. Trading Halt Recommended."
    elif degradeds:
        banner_msg = f"{degradeds[0][0]} Degraded. Review immediately."
    elif watches:
        banner_msg = f"{watches[0][0]} Watch. Monitoring required."
        
    if overall_h["status"] == "WARMING_UP":
        banner_msg = "System warming up. Gathering data."
        
    st.markdown(
        f"<div style='border: 1px solid {banner_color}; border-left: 6px solid {banner_color}; border-radius: 4px; padding: 15px; background: #0f1629; margin-bottom: 20px;'>"
        f"<h3 style='margin: 0; color: {banner_color}; font-family: \"IBM Plex Mono\", monospace;'>{banner_icon} SYSTEM STATUS: {overall_h['status']}</h3>"
        f"<p style='margin: 5px 0 0 0; color: #e2e8f0;'>{banner_msg}</p>"
        f"</div>",
        unsafe_allow_html=True
    )
        
    # --- Save Snapshot & Render History ---
    try:
        from gqos.dashboard.health_history import save_snapshot, get_history
        metrics_dict = {
            'overall_edge': overall_h.get('score'),
            'alpha_health': alpha_h.get('score'),
            'execution_health': exec_h.get('score'),
            'risk_health': risk_h.get('score'),
            'learning_health': learn_h.get('score'),
            'overall_status': overall_h.get('status'),
            'alpha_status': alpha_h.get('status'),
            'execution_status': exec_h.get('status'),
            'risk_status': risk_h.get('status'),
            'learning_status': learn_h.get('status'),
            'confidence': f"Alpha:{alpha_h.get('confidence')} Exec:{exec_h.get('confidence')} Risk:{risk_h.get('confidence')} Learn:{learn_h.get('confidence')}",
            'reason_summary': banner_msg
        }
        save_snapshot(metrics_dict)
        
        df_hist = get_history(hours=24)
        if not df_hist.empty:
            st.markdown("### 📈 Health History (24h)")
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(x=df_hist['timestamp'], y=df_hist['overall_edge'], mode='lines', name='Overall Edge', line=dict(color='#38bdf8', width=3)))
            fig.add_trace(go.Scatter(x=df_hist['timestamp'], y=df_hist['alpha_health'], mode='lines', name='Alpha', line=dict(color='#4ade80', width=1, dash='dot')))
            fig.add_trace(go.Scatter(x=df_hist['timestamp'], y=df_hist['execution_health'], mode='lines', name='Execution', line=dict(color='#facc15', width=1, dash='dot')))
            fig.add_trace(go.Scatter(x=df_hist['timestamp'], y=df_hist['risk_health'], mode='lines', name='Risk', line=dict(color='#f87171', width=1, dash='dot')))
            fig.add_trace(go.Scatter(x=df_hist['timestamp'], y=df_hist['learning_health'], mode='lines', name='Learning', line=dict(color='#a78bfa', width=1, dash='dot')))
            
            fig.update_layout(
                template='plotly_dark',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(range=[0, 105], title="Score"),
                margin=dict(l=0, r=0, t=30, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("---")
            
    except Exception as e:
        st.warning(f"Could not load Health History: {e}")
        
    def render_health_card(title, health_dict):
        score = health_dict.get("score")
        status = health_dict.get("status", "WARMING_UP")
        trend = health_dict.get("trend")
        conf = health_dict.get("confidence", "LOW")
        color = status_color(status)
        
        score_str = f"{score:.0f}" if score is not None else "-"
        
        trend_html = ""
        if trend is not None and score is not None:
            t_color = "#4ade80" if trend >= 0 else "#f87171"
            t_arrow = "↑" if trend >= 0 else "↓"
            trend_html = f"<span style='color: {t_color}; font-size: 0.9rem; margin-left: 5px;'>{t_arrow} {abs(trend):.1f}</span>"
            
        conf_html = f"<div style='font-size: 0.7rem; color: #475569; margin-top: 8px;'>CONFIDENCE: {conf}</div>"
        
        st.markdown(
            f"<div style='border: 1px solid #1e2d4a; border-radius: 8px; padding: 15px; background: #0f1629; text-align: center;'>"
            f"<div style='font-size: 0.9rem; color: #94a3b8; font-family: \"IBM Plex Sans\", sans-serif; margin-bottom: 5px;'>{title}</div>"
            f"<div style='font-size: 2rem; color: {color}; font-family: \"IBM Plex Mono\", monospace; font-weight: bold;'>{score_str}{trend_html}</div>"
            f"<div style='font-size: 0.8rem; color: {color}; font-family: \"IBM Plex Mono\", monospace; margin-top: 5px;'>{status}</div>"
            f"{conf_html}"
            f"</div>",
            unsafe_allow_html=True
        )

    # Top level metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: render_health_card("Overall Edge", overall_h)
    with c2: render_health_card("Alpha Health", alpha_h)
    with c3: render_health_card("Execution", exec_h)
    with c4: render_health_card("Risk Health", risk_h)
    with c5: render_health_card("Learning", learn_h)
    
    st.markdown("---")
    
    col_radar, col_table = st.columns([1, 2])
    
    with col_radar:
        st.markdown("### Health Dimensions")
        categories = ['Alpha', 'Execution', 'Risk', 'Learning']
        
        scores = [
            alpha_h["score"] or 0, 
            exec_h["score"] or 0, 
            risk_h["score"] or 0, 
            learn_h["score"] or 0
        ]
        
        marker_colors = [
            status_color(alpha_h["status"]),
            status_color(exec_h["status"]),
            status_color(risk_h["status"]),
            status_color(learn_h["status"])
        ]
        
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=scores,
            theta=categories,
            fill='toself',
            fillcolor='rgba(56,189,248,0.1)',
            line=dict(color='#475569', width=1),
            marker=dict(size=12, color=marker_colors),
            mode='lines+markers',
            text=[f"{s:.0f}" if s else "WARMING_UP" for s in scores],
            hoverinfo="text"
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], color="#475569", gridcolor="#1e2d4a"),
                angularaxis=dict(color="#e2e8f0", gridcolor="#1e2d4a")
            ),
            paper_bgcolor="#0a0e1a", plot_bgcolor="#0a0e1a",
            margin=dict(l=40, r=40, t=20, b=20),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
        
    with col_table:
        st.markdown("### Dimension Breakdown")
        
        rows = []
        for dim_name, h_dict in [
            ("Alpha Health", alpha_h),
            ("Execution Health", exec_h),
            ("Risk Health", risk_h),
            ("Learning Health", learn_h)
        ]:
            if h_dict.get("metrics"):
                metrics_str = " | ".join(f"{k}: {v}" for k, v in h_dict["metrics"].items())
            else:
                metrics_str = "-"
                
            score_val = f"{h_dict['score']:.0f}" if h_dict.get("score") is not None else "-"
            conf = h_dict.get("confidence", "-")
            
            rows.append({
                "Dimension": dim_name,
                "Score": score_val,
                "Status": h_dict["status"],
                "Confidence": conf,
                "Key Metrics": metrics_str,
                "Reason/Note": h_dict.get("reason", "")
            })
            
        df_breakdown = pd.DataFrame(rows)
        
        def highlight_status(s):
            if s == "HEALTHY": return "color: #4ade80; font-weight: bold"
            if s == "WATCH": return "color: #facc15; font-weight: bold"
            if s == "DEGRADED": return "color: #f97316; font-weight: bold"
            if s == "CRITICAL": return "color: #f87171; font-weight: bold"
            return "color: #94a3b8"
            
        def highlight_conf(c):
            if "HIGH" in str(c): return "color: #4ade80"
            if "LOW" in str(c): return "color: #f87171"
            return "color: #facc15"
            
        st.dataframe(
            df_breakdown.style.map(highlight_status, subset=["Status"])
                              .map(highlight_conf, subset=["Confidence"]),
            use_container_width=True, hide_index=True
        )
 
# ── Footer ─────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<small style='color:#334155'>GQOS TradePro • Pattern Promotion Dashboard • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</small>",
    unsafe_allow_html=True,
)
