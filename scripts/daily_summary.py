"""Daily performance summary for the GQOS live bot.

Reads live trade outcomes and reports win rate, expectancy, PnL, profit factor
and max drawdown — split into STRATEGY trades (a real discovered pattern was
matched) vs EXPLORATION/probe trades (no pattern). Judging the bot by the
combined number is misleading because exploration intentionally takes low-edge
trades to gather data.

Usage:
    python -m scripts.daily_summary            # all history
    python -m scripts.daily_summary --days 1   # last 24h only
"""
import os
import json
import argparse
from datetime import datetime, timedelta, timezone

OUTCOMES_PATH = os.getenv("GQOS_OUTCOMES_PATH", "data/learning/live_outcomes.jsonl")


def _num(rec, *keys):
    for k in keys:
        v = rec.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def _parse_ts(rec):
    for k in ("close_time", "open_time"):
        v = rec.get(k)
        if not v:
            continue
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


def _load(days=None):
    if not os.path.exists(OUTCOMES_PATH):
        return []
    rows = []
    cutoff = None
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with open(OUTCOMES_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if cutoff is not None:
                ts = _parse_ts(r)
                if ts is not None:
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts < cutoff:
                        continue
            rows.append(r)
    return rows


def _metrics(rows):
    pnls = [(_num(r, "realized_pnl", "pnl"), _num(r, "actual_r")) for r in rows]
    pnls = [(p, r) for p, r in pnls if p is not None]
    n = len(pnls)
    if n == 0:
        return None
    wins = [p for p, _ in pnls if p > 0]
    losses = [p for p, _ in pnls if p <= 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    rs = [r for _, r in pnls if r is not None]
    # equity curve max drawdown
    eq = 0.0
    peak = 0.0
    max_dd = 0.0
    for p, _ in pnls:
        eq += p
        peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)
    return {
        "n": n,
        "win_rate": len(wins) / n * 100,
        "wins": len(wins),
        "losses": len(losses),
        "total_pnl": sum(p for p, _ in pnls),
        "avg_pnl": sum(p for p, _ in pnls) / n,
        "avg_r": (sum(rs) / len(rs)) if rs else None,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        "max_drawdown": max_dd,
    }


def _fmt(title, m):
    if not m:
        print(f"\n{title}: (no trades)")
        return
    pf = "inf" if m["profit_factor"] == float("inf") else f"{m['profit_factor']:.2f}"
    avg_r = "n/a" if m["avg_r"] is None else f"{m['avg_r']:+.3f}"
    print(f"\n{title}")
    print(f"  trades      : {m['n']}  ({m['wins']}W / {m['losses']}L)")
    print(f"  win rate    : {m['win_rate']:.1f}%")
    print(f"  total PnL   : {m['total_pnl']:+.2f}")
    print(f"  avg PnL/trade: {m['avg_pnl']:+.3f}")
    print(f"  avg R       : {avg_r}")
    print(f"  profit factor: {pf}")
    print(f"  max drawdown: {m['max_drawdown']:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None, help="Only include trades from the last N days")
    args = ap.parse_args()

    rows = _load(args.days)
    scope = f"last {args.days} day(s)" if args.days else "all history"
    print(f"=== GQOS Daily Summary ({scope}) — source: {OUTCOMES_PATH} ===")

    strategy = [r for r in rows if str(r.get("pattern_id") or "").strip()]
    exploration = [r for r in rows if not str(r.get("pattern_id") or "").strip()]

    _fmt("STRATEGY (real pattern matched) *** judge the bot by this ***", _metrics(strategy))
    _fmt("EXPLORATION / probe (no pattern — data gathering)", _metrics(exploration))
    _fmt("COMBINED (all trades)", _metrics(rows))


if __name__ == "__main__":
    main()
