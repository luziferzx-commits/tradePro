import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import MetaTrader5 as mt5
import yaml
from market.session_detector import SessionDetector

logger = logging.getLogger("GQOS.ContinuousMarketSim")

OBS_PATH = Path(os.getenv("GQOS_MARKET_OBSERVATIONS_PATH", "data/learning/market_observations.jsonl"))
PENDING_PATH = Path(os.getenv("GQOS_VIRTUAL_PENDING_PATH", "data/learning/virtual_trades.json"))
OUTCOMES_PATH = Path(os.getenv("GQOS_VIRTUAL_OUTCOMES_PATH", "data/learning/virtual_trade_outcomes.jsonl"))
STATE_PATH = Path(os.getenv("GQOS_MARKET_SIM_STATE_PATH", "data/learning/continuous_market_sim_state.json"))

TIMEFRAME = mt5.TIMEFRAME_M1
MAX_PENDING = int(os.getenv("GQOS_VIRTUAL_MAX_PENDING", "5000"))
HORIZON_BARS = int(os.getenv("GQOS_VIRTUAL_HORIZON_BARS", "240"))


class ContinuousMarketSimulator:
    """
    Records every new M1 candle for enabled markets and runs neutral BUY/SELL
    virtual trades. This is intentionally separate from live outcomes so
    simulated data can improve analysis without contaminating real PnL learning.
    """

    def __init__(self):
        self._aliases, self._symbols = self._load_symbol_config()

    def scan_once(self) -> dict[str, int]:
        if os.getenv("ENABLE_CONTINUOUS_MARKET_SIM", "True").lower() not in {"1", "true", "yes"}:
            return {"observations": 0, "opened": 0, "closed": 0}

        state = self._load_json(STATE_PATH, {})
        pending = self._load_json(PENDING_PATH, {})
        if not isinstance(pending, dict):
            pending = {}

        observations = 0
        opened = 0
        for clean_symbol, cfg in self._symbols.items():
            if not cfg.get("enabled", False):
                continue
            symbol = self._aliases.get(clean_symbol, clean_symbol)
            rows = self._latest_closed_bars(symbol, count=60)
            if not rows:
                continue

            latest = rows[-1]
            bar_time = int(latest["time"])
            state_key = f"{symbol}:M1:last_bar"
            if int(state.get(state_key, 0) or 0) >= bar_time:
                continue

            obs = self._build_observation(clean_symbol, symbol, latest, rows, cfg)
            self._append_jsonl(OBS_PATH, obs)
            observations += 1
            state[state_key] = bar_time

            opened += self._open_virtual_trades(obs, pending)

        closed = self._process_pending(pending)
        self._trim_pending(pending)
        self._save_json(PENDING_PATH, pending)
        self._save_json(STATE_PATH, state)
        if observations or opened or closed:
            logger.info(
                "[ContinuousMarketSim] observations=%s opened=%s closed=%s pending=%s",
                observations,
                opened,
                closed,
                len(pending),
            )
        return {"observations": observations, "opened": opened, "closed": closed}

    def process_pending(self) -> int:
        pending = self._load_json(PENDING_PATH, {})
        if not isinstance(pending, dict):
            return 0
        closed = self._process_pending(pending)
        self._trim_pending(pending)
        self._save_json(PENDING_PATH, pending)
        return closed

    def _latest_closed_bars(self, symbol: str, count: int) -> list[Any]:
        if not mt5.symbol_select(symbol, True):
            return []
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 1, count)
        if rates is None or len(rates) == 0:
            return []
        return list(rates)

    def _build_observation(self, clean_symbol: str, symbol: str, bar, rows, cfg: dict) -> dict[str, Any]:
        closes = [float(r["close"]) for r in rows]
        atr = self._atr(rows)
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        spread = int(getattr(info, "spread", 0) or 0) if info else None
        typical_spread = float(cfg.get("typical_spread_points", 0) or 0)
        close = float(bar["close"])
        atr_pct = (atr / close * 100.0) if atr and close > 0 else None
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "bar_time": datetime.fromtimestamp(int(bar["time"]), timezone.utc).isoformat(),
            "symbol": symbol,
            "clean_symbol": clean_symbol,
            "timeframe": "M1",
            "open": float(bar["open"]),
            "high": float(bar["high"]),
            "low": float(bar["low"]),
            "close": close,
            "tick_volume": int(bar["tick_volume"]),
            "spread": spread,
            "spread_bucket": self._spread_bucket(spread, typical_spread),
            "bid": float(getattr(tick, "bid", 0.0) or 0.0) if tick else None,
            "ask": float(getattr(tick, "ask", 0.0) or 0.0) if tick else None,
            "atr_14": atr,
            "atr_pct": atr_pct,
            "volatility_bucket": self._volatility_bucket(atr_pct),
            "session": self._session_from_bar_time(int(bar["time"])),
            "market_session": self._market_session_from_bar_time(int(bar["time"]), cfg),
            "return_1": (closes[-1] / closes[-2] - 1.0) if len(closes) >= 2 and closes[-2] else None,
            "sma_20": sum(closes[-20:]) / min(20, len(closes)) if closes else None,
            "atr_sl_multiplier": float(cfg.get("atr_sl_multiplier", 5.0)),
        }

    def _open_virtual_trades(self, obs: dict[str, Any], pending: dict[str, dict]) -> int:
        symbol = obs["symbol"]
        entry = float(obs["close"])
        atr = float(obs.get("atr_14") or 0.0)
        info = mt5.symbol_info(symbol)
        point = float(getattr(info, "point", 0.0) or 0.0) if info else 0.0
        if entry <= 0 or point <= 0:
            return 0
        buffer = atr * float(obs.get("atr_sl_multiplier") or 5.0) if atr > 0 else point * 500
        buffer = max(buffer, point * 50)

        opened = 0
        for side in ("BUY", "SELL"):
            key = f"{symbol}:M1:{obs['bar_time']}:{side}"
            if key in pending:
                continue
            if side == "BUY":
                sl = entry - buffer
                tp = entry + (buffer * 2.0)
            else:
                sl = entry + buffer
                tp = entry - (buffer * 2.0)
            pending[key] = {
                "key": key,
                "symbol": symbol,
                "clean_symbol": obs["clean_symbol"],
                "side": side,
                "timeframe": "M1",
                "entry_time": obs["bar_time"],
                "entry_price": entry,
                "sl_price": sl,
                "tp_price": tp,
                "atr_14": obs.get("atr_14"),
                "atr_pct": obs.get("atr_pct"),
                "spread": obs.get("spread"),
                "spread_bucket": obs.get("spread_bucket"),
                "volatility_bucket": obs.get("volatility_bucket"),
                "session": obs.get("session"),
                "market_session": obs.get("market_session"),
                "sim_type": "CONTINUOUS_M1_BOTH_SIDES",
                "status": "OPEN",
            }
            opened += 1
        return opened

    def _process_pending(self, pending: dict[str, dict]) -> int:
        closed = 0
        for key, row in list(pending.items()):
            outcome = self._evaluate(row)
            if not outcome:
                continue
            pending.pop(key, None)
            self._append_jsonl(OUTCOMES_PATH, outcome)
            closed += 1
        return closed

    def _evaluate(self, row: dict[str, Any]) -> dict[str, Any] | None:
        symbol = row["symbol"]
        side = row["side"]
        try:
            entry_dt = datetime.fromisoformat(str(row["entry_time"]).replace("Z", "+00:00"))
        except Exception:
            return None
        rates = mt5.copy_rates_range(symbol, TIMEFRAME, entry_dt, datetime.now(timezone.utc))
        if rates is None or len(rates) <= 1:
            return None

        entry = float(row["entry_price"])
        sl = float(row["sl_price"])
        tp = float(row["tp_price"])
        outcome = None
        close_price = None
        close_time = None

        for idx, candle in enumerate(list(rates)[1:], start=1):
            high = float(candle["high"])
            low = float(candle["low"])
            if side == "BUY":
                hit_sl = low <= sl
                hit_tp = high >= tp
            else:
                hit_sl = high >= sl
                hit_tp = low <= tp
            if hit_sl and hit_tp:
                outcome, close_price = "LOSS_BOTH_HIT", sl
            elif hit_sl:
                outcome, close_price = "LOSS", sl
            elif hit_tp:
                outcome, close_price = "WIN", tp
            elif idx >= HORIZON_BARS:
                close_price = float(candle["close"])
                outcome = "TIMEOUT_WIN" if self._signed_r(side, entry, close_price, sl) > 0 else "TIMEOUT_LOSS"
            if outcome:
                close_time = datetime.fromtimestamp(int(candle["time"]), timezone.utc).isoformat()
                break

        if not outcome:
            return None
        actual_r = self._signed_r(side, entry, close_price, sl)
        return {
            **row,
            "status": "CLOSED",
            "outcome": outcome,
            "close_price": close_price,
            "close_time": close_time,
            "actual_r": round(actual_r, 4),
            "sim_learning_source": "CONTINUOUS_MARKET_SIM",
        }

    def _signed_r(self, side: str, entry: float, close: float, sl: float) -> float:
        risk = abs(entry - sl)
        if risk <= 0:
            return 0.0
        pnl = close - entry if side == "BUY" else entry - close
        return pnl / risk

    def _atr(self, rows) -> float | None:
        if len(rows) < 15:
            return None
        trs = []
        prev_close = None
        for candle in rows:
            high = float(candle["high"])
            low = float(candle["low"])
            close = float(candle["close"])
            tr = high - low if prev_close is None else max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
            prev_close = close
        return sum(trs[-14:]) / 14.0 if trs else None

    def _session_from_bar_time(self, timestamp: int) -> str:
        return SessionDetector.detect(float(timestamp))

    def _market_session_from_bar_time(self, timestamp: int, cfg: dict) -> str:
        hour = datetime.fromtimestamp(timestamp, timezone.utc).hour
        asset_class = str(cfg.get("asset_class", "")).upper()
        listed_session = str(cfg.get("session", "")).upper()
        if asset_class == "CRYPTO":
            if 0 <= hour < 7:
                return "CRYPTO_ASIA"
            if 7 <= hour < 13:
                return "CRYPTO_EU"
            if 13 <= hour < 21:
                return "CRYPTO_US"
            return "CRYPTO_ROLLOVER"
        if listed_session == "US":
            if 13 <= hour < 14:
                return "US_PRE_CASH"
            if 14 <= hour < 20:
                return "US_CASH"
            if 20 <= hour < 22:
                return "US_LATE"
            return "US_OFF_HOURS"
        if listed_session == "EU":
            if 7 <= hour < 9:
                return "EU_OPEN"
            if 9 <= hour < 13:
                return "EU_CORE"
            if 13 <= hour < 16:
                return "EU_US_OVERLAP"
            return "EU_OFF_HOURS"
        if 0 <= hour < 7:
            return "ASIA_RANGE"
        if 7 <= hour < 13:
            return "LONDON_FLOW"
        if 13 <= hour < 16:
            return "LONDON_NY_OVERLAP"
        if 16 <= hour < 21:
            return "NY_FLOW"
        return "ROLLOVER"

    def _spread_bucket(self, spread: int | None, typical_spread: float) -> str:
        if spread is None or typical_spread <= 0:
            return "UNKNOWN"
        ratio = float(spread) / typical_spread
        if ratio <= 0.8:
            return "TIGHT"
        if ratio <= 1.5:
            return "NORMAL"
        if ratio <= 3.0:
            return "WIDE"
        return "EXTREME"

    def _volatility_bucket(self, atr_pct: float | None) -> str:
        if atr_pct is None:
            return "UNKNOWN"
        if atr_pct < 0.03:
            return "LOW"
        if atr_pct < 0.12:
            return "NORMAL"
        if atr_pct < 0.35:
            return "HIGH"
        return "EXTREME"

    def _trim_pending(self, pending: dict[str, dict]):
        if len(pending) <= MAX_PENDING:
            return
        for key, _ in sorted(pending.items(), key=lambda item: item[1].get("entry_time", ""))[: len(pending) - MAX_PENDING]:
            pending.pop(key, None)

    def _load_symbol_config(self):
        try:
            with open("config/symbols.yaml", "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            return cfg.get("symbol_aliases", {}), cfg.get("symbols", {})
        except Exception:
            return {}, {}

    def _load_json(self, path: Path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return default

    def _save_json(self, path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _append_jsonl(self, path: Path, row: dict[str, Any]):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")


continuous_market_simulator = ContinuousMarketSimulator()
