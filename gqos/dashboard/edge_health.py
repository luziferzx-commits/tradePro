import pandas as pd
from datetime import datetime, timedelta

def status_from_score(score: float) -> str:
    if score is None or pd.isna(score):
        return "WARMING_UP"
    if score >= 80:
        return "HEALTHY"
    elif score >= 60:
        return "WATCH"
    elif score >= 40:
        return "DEGRADED"
    else:
        return "CRITICAL"

def calc_alpha_health(df_out: pd.DataFrame) -> dict:
    result = {
        "score": None,
        "status": "WARMING_UP",
        "reason": "Insufficient live trades (< 10)",
        "metrics": {},
        "confidence": "LOW",
        "trend": None
    }
    
    if df_out is None or df_out.empty or len(df_out) < 10:
        if df_out is not None and not df_out.empty:
            result["metrics"]["Trades"] = f"{len(df_out)}"
        return result
        
    required_cols = ["outcome"]
    if not all(col in df_out.columns for col in required_cols):
        result["reason"] = "Missing outcome column"
        return result
        
    total = len(df_out)
    wins = len(df_out[df_out["outcome"] == "WIN"])
    win_rate_pct = (wins / total * 100) if total > 0 else 0
    
    # Confidence based on trades
    if total < 30:
        result["confidence"] = f"LOW ({total}/30 trades)"
    elif total <= 100:
        result["confidence"] = f"MEDIUM ({total}/100 trades)"
    else:
        result["confidence"] = f"HIGH ({total} trades)"
    
    # Calculate avg_r
    avg_r = 0.0
    if "actual_r" in df_out.columns:
        avg_r = df_out["actual_r"].dropna().mean()
        if pd.isna(avg_r): avg_r = 0.0
    elif "realized_r" in df_out.columns:
        avg_r = df_out["realized_r"].dropna().mean()
        if pd.isna(avg_r): avg_r = 0.0
        
    # Calculate profit factor
    profit_factor = 0.0
    if "realized_pnl" in df_out.columns:
        gross_profit = df_out[df_out["realized_pnl"] > 0]["realized_pnl"].sum()
        gross_loss = abs(df_out[df_out["realized_pnl"] < 0]["realized_pnl"].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (1.0 if gross_profit == 0 else 5.0)
    elif "pattern_pf" in df_out.columns:
        profit_factor = df_out["pattern_pf"].dropna().mean()
        if pd.isna(profit_factor): profit_factor = 0.0
        
    result["metrics"] = {
        "Win Rate": f"{win_rate_pct:.1f}%",
        "Avg R": f"{avg_r:.2f}R",
        "Profit Factor": f"{profit_factor:.2f}"
    }
    
    # Components with Clamping
    wr_score = min(100.0, max(0.0, win_rate_pct * 1.5))
    avgr_score = min(100.0, max(0.0, 50.0 + avg_r * 50.0))
    pf_score = min(100.0, max(0.0, profit_factor * 50.0))
    
    final_score = (wr_score + avgr_score + pf_score) / 3.0
    final_score = min(100.0, max(0.0, final_score))
    
    result["score"] = final_score
    result["status"] = status_from_score(final_score)
    result["reason"] = f"WR {win_rate_pct:.1f}%, PF {profit_factor:.2f}, AvgR {avg_r:.2f}"
    
    return result

def calc_execution_health(df_slip: pd.DataFrame) -> dict:
    result = {
        "score": None,
        "status": "WARMING_UP",
        "reason": "No slippage data",
        "metrics": {},
        "confidence": "LOW",
        "trend": None
    }
    
    if df_slip is None or df_slip.empty:
        return result
        
    total = len(df_slip)
    if total < 30:
        result["confidence"] = f"LOW ({total}/30 trades)"
    elif total <= 100:
        result["confidence"] = f"MEDIUM ({total}/100 trades)"
    else:
        result["confidence"] = f"HIGH ({total} trades)"
        
    avg_slip = 0.0
    if "slippage_pips" in df_slip.columns:
        avg_slip = df_slip["slippage_pips"].dropna().mean()
    elif "Avg Slippage (Pips)" in df_slip.columns:
        avg_slip = df_slip["Avg Slippage (Pips)"].dropna().mean()
        
    if pd.isna(avg_slip): avg_slip = 0.0
        
    avg_exec_time = 0.0
    if "execution_time_ms" in df_slip.columns:
        avg_exec_time = df_slip["execution_time_ms"].dropna().mean()
    elif "Avg Exec Time" in df_slip.columns:
        avg_exec_time = df_slip["Avg Exec Time"].dropna().mean()
        
    if pd.isna(avg_exec_time): avg_exec_time = 0.0
        
    result["metrics"] = {
        "Avg Slippage": f"{avg_slip:.2f} pips",
        "Avg Latency": f"{avg_exec_time:.0f} ms"
    }
    
    slip_score = min(100.0, max(0.0, 100.0 - (avg_slip * 40.0)))
    lat_score = min(100.0, max(0.0, 100.0 - (avg_exec_time / 10.0)))
    
    final_score = min(100.0, max(0.0, (slip_score + lat_score) / 2.0))
    
    result["score"] = final_score
    result["status"] = status_from_score(final_score)
    result["reason"] = f"Latency {avg_exec_time:.0f}ms, Slip {avg_slip:.2f} pips"
    
    return result

def calc_risk_health(account_data, pos_list=None) -> dict:
    result = {
        "score": None,
        "status": "WARMING_UP",
        "reason": "MT5 not connected",
        "metrics": {},
        "confidence": "LOW",
        "trend": None
    }
    
    if account_data is None:
        return result
        
    result["confidence"] = "HIGH (MT5 Live)"  # If we have MT5 data, it's highly reliable
        
    # extract balance, equity, margin
    try:
        balance = account_data.balance
        equity = account_data.equity
        margin = account_data.margin
    except AttributeError:
        # Fallback for mock/dict data in tests
        if isinstance(account_data, dict):
            balance = account_data.get("balance", 0.0)
            equity = account_data.get("equity", 0.0)
            margin = account_data.get("margin", 0.0)
        else:
            balance = 0.0
            equity = 0.0
            margin = 0.0
            
    if balance == 0:
        return result
        
    margin_pct = (margin / balance) * 100.0
    drawdown_pct = ((equity - balance) / balance) * 100.0
    
    # Calculate open risk pct if positions provided
    open_risk_pct = None
    if pos_list is not None and len(pos_list) > 0:
        total_risk_usd = 0.0
        for p in pos_list:
            try:
                # We will rely on actual risk attribute if injected
                risk_usd = getattr(p, "risk_usd", 0.0)
                if risk_usd == 0.0 and isinstance(p, dict):
                    risk_usd = p.get("risk_usd", 0.0)
                total_risk_usd += risk_usd
            except Exception:
                pass
        
        if total_risk_usd > 0:
            open_risk_pct = (total_risk_usd / balance) * 100.0

    # Components (clamped)
    scores = []
    margin_score = min(100.0, max(0.0, 100.0 - (margin_pct * 5.0)))
    scores.append(margin_score)
    
    dd_score = min(100.0, max(0.0, 100.0 + (drawdown_pct * 20.0)))
    scores.append(dd_score)
    
    result["metrics"] = {
        "Margin Used": f"{margin_pct:.1f}%",
        "Floating PnL": f"{drawdown_pct:.1f}%"
    }
    
    reason_parts = [f"Margin {margin_pct:.1f}%", f"Float {drawdown_pct:.1f}%"]
    
    if open_risk_pct is not None:
        risk_score = min(100.0, max(0.0, 100.0 - (open_risk_pct * 10.0)))
        scores.append(risk_score)
        result["metrics"]["Open Risk"] = f"{open_risk_pct:.1f}%"
        reason_parts.append(f"Risk {open_risk_pct:.1f}%")
    else:
        result["metrics"]["Open Risk"] = "PENDING"
        reason_parts.append("Risk PENDING")
        
    final_score = min(100.0, max(0.0, sum(scores) / len(scores)))
    
    result["score"] = final_score
    result["status"] = status_from_score(final_score)
    result["reason"] = " | ".join(reason_parts)
    
    return result

def calc_learning_health(df_pat: pd.DataFrame, df_out: pd.DataFrame) -> dict:
    result = {
        "score": None,
        "status": "WARMING_UP",
        "reason": "No pattern DB",
        "metrics": {},
        "confidence": "LOW",
        "trend": None
    }
    
    if df_pat is None or df_pat.empty:
        return result
        
    total_patterns = len(df_pat)
    if total_patterns < 1000:
        result["confidence"] = f"LOW ({total_patterns}/1k pats)"
    elif total_patterns <= 10000:
        result["confidence"] = f"MEDIUM ({total_patterns}/10k pats)"
    else:
        result["confidence"] = f"HIGH ({total_patterns} pats)"
        
    validated_statuses = ["LIVE_APPROVED", "SHADOW_PASSED", "RESEARCH_VALIDATED"]
    
    if "promotion_status" in df_pat.columns:
        val_count = len(df_pat[df_pat["promotion_status"].isin(validated_statuses)])
    else:
        val_count = 0
        
    val_pct = (val_count / total_patterns * 100.0) if total_patterns > 0 else 0.0
    
    # Calculate retrain readiness
    total_trades = len(df_out) if (df_out is not None and not df_out.empty) else 0
    trades_since_retrain = total_trades % 50
    retrain_progress_pct = (trades_since_retrain / 50.0) * 100.0
    
    pipeline_score = min(100.0, max(0.0, val_pct * 10.0)) # Assume 10% validated is perfect
    
    # Do not penalize score for retrain reset. Use pipeline score as primary, slightly boost for readiness
    final_score = pipeline_score
    if final_score < 100:
        final_score = min(100.0, final_score + (retrain_progress_pct * 0.1))
        
    final_score = min(100.0, max(0.0, final_score))
        
    result["metrics"] = {
        "Validated Patterns": f"{val_pct:.1f}%",
        "Retrain Readiness": f"{retrain_progress_pct:.0f}%"
    }
    
    result["score"] = final_score
    result["status"] = status_from_score(final_score)
    result["reason"] = f"{val_pct:.1f}% valid, {retrain_progress_pct:.0f}% to retrain"
    
    return result

def calc_overall_edge_health(alpha_dict, exec_dict, risk_dict, learn_dict) -> dict:
    weights = {
        "alpha": 0.35,
        "exec": 0.25,
        "risk": 0.30,
        "learn": 0.10
    }
    
    scores = {
        "alpha": alpha_dict.get("score"),
        "exec": exec_dict.get("score"),
        "risk": risk_dict.get("score"),
        "learn": learn_dict.get("score")
    }
    
    # Filter out None
    valid_scores = {k: v for k, v in scores.items() if v is not None and not pd.isna(v)}
    
    if not valid_scores:
        return {
            "score": None,
            "status": "WARMING_UP",
            "reason": "All systems warming up",
            "metrics": {},
            "trend": None
        }
        
    # Redistribute weights
    total_valid_weight = sum(weights[k] for k in valid_scores.keys())
    
    weighted_sum = 0.0
    for k, v in valid_scores.items():
        normalized_weight = weights[k] / total_valid_weight
        weighted_sum += v * normalized_weight
        
    final_score = min(100.0, max(0.0, weighted_sum))
    
    # Calculate overall trend if available
    trends = []
    statuses = []
    
    for d in [alpha_dict, exec_dict, risk_dict, learn_dict]:
        if d.get("trend") is not None:
            trends.append(d["trend"])
        if d.get("status") and d.get("status") != "WARMING_UP":
            statuses.append(d.get("status"))
            
    avg_trend = sum(trends) / len(trends) if trends else None
    
    # Base status on final score
    status = status_from_score(final_score)
    
    # Override status if there is a weaker link
    if "CRITICAL" in statuses:
        status = "CRITICAL"
    elif "DEGRADED" in statuses and status not in ["CRITICAL"]:
        status = "DEGRADED"
    elif "WATCH" in statuses and status not in ["CRITICAL", "DEGRADED"]:
        status = "WATCH"

    
    return {
        "score": final_score,
        "status": status,
        "reason": f"System is {status}",
        "metrics": {},
        "trend": avg_trend
    }
