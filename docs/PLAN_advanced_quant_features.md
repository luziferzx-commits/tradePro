# Plan: Advanced Quant Features (Smart Execution / Dynamic TP-SL / Auto Walk-Forward)

**Status:** PLANNED — NOT IMPLEMENTED. No code has been changed for this plan.
**Date:** 2026-06-29
**Context:** An earlier draft of this plan (from another tool) targeted files that are not part of the live execution path (`scripts/run_gqos_live.py`). This version corrects the targets against the actual live code and records the decisions made.

---

## Decisions made

| Feature | Decision |
|---|---|
| Auto Walk-Forward (promotion/decay) | Add a Telegram confirm-gate to the **existing** live system for `LIVE_APPROVED` promotions only. `DEMOTED` stays fully automatic. Do **not** build a new parallel script. |
| Smart Execution | Entries only, 5-minute limit-order expiry, as originally proposed. Exits always stay market orders. |
| Dynamic TP/SL (ML) | Deploy live directly (no shadow-mode delay), but hard min/max distance clamps are mandatory as a safety bound on model output. |

---

## 1. Auto Walk-Forward / Promotion Gate

**Finding:** This feature already exists and is already running live — it is not new work. `gqos/learning/pattern_updater.py` (`PatternConfidenceUpdater._evaluate_promotion`) computes Bayesian-decayed rolling PF/WR per pattern across five tiers (`REJECTED → RESEARCH_DISCOVERED → RESEARCH_VALIDATED → SHADOW_PASSED → LIVE_APPROVED`, plus `DEMOTED`), and `gqos/learning/retrain_trigger.py::_run_retrain()` calls it automatically every `retrain_threshold` (currently 200) closed trades. This is wired into the same `retrain_trigger` instance that `scripts/run_gqos_live.py` already uses via `on_realized_pnl` → `retrain_trigger.on_trade_closed(...)`.

**What actually needs to change:**
- `gqos/learning/pattern_updater.py::_evaluate_promotion()` (lines 140–152): when a pattern's new status would be `LIVE_APPROVED` but its *previous* status was not, do not write it immediately. Instead return/flag it as `PENDING_APPROVAL` and leave the old status in place until confirmed.
- `gqos/learning/retrain_trigger.py::_run_retrain()` (lines 112–119, where `pattern_updater.update()` is called): after the update, collect any patterns that just flipped to `PENDING_APPROVAL` and send a Telegram message (reuse `notifications/telegram_notifier.py` send path) with the pattern id, old/new PF, win rate, and sample size.
- Add an inbound Telegram command/callback (the existing `notifications/telegram_listener.py::TelegramCommandListener` already has a callback-registration pattern used for bot shutdown — extend it) to approve/reject a pending promotion. On approve, write `LIVE_APPROVED` to `pattern_database.parquet`; on reject/timeout, leave it at `SHADOW_PASSED`.
- `DEMOTED` transitions skip this gate entirely and write immediately, since they only reduce risk.

**Open question to resolve before coding:** how long should a `PENDING_APPROVAL` wait before defaulting to reject (no response = stay demoted/shadow, not silently approved)?

---

## 2. Smart Execution (Entry Limit Orders)

**Finding:** The original plan targeted `execution/executor.py`, which is dead code with respect to the live bot — it's only imported by `main.py` and the legacy `run_evidence_live.py` / `run_abc_shadow_session.py` scripts. The actual live order-send path is `gqos/live/adapters/mt5_adapter.py::submit_order()` (line 82), which currently hardcodes `mt5.TRADE_ACTION_DEAL` + `mt5.ORDER_TYPE_BUY`/`ORDER_TYPE_SELL` (market orders only, line ~168–187).

**What needs to change:**
- `config/settings.py`: add `USE_SMART_EXECUTION = True`, `LIMIT_ORDER_EXPIRY_MINUTES = 5`.
- `gqos/live/adapters/mt5_adapter.py::submit_order()`: add an `is_entry: bool` parameter (or infer from caller). When `USE_SMART_EXECUTION` is on and this is an entry, send `ORDER_TYPE_BUY_LIMIT`/`ORDER_TYPE_SELL_LIMIT` at mid-price with `action=mt5.TRADE_ACTION_PENDING`, `type_time=mt5.ORDER_TIME_SPECIFIED`, and `expiration` set to now + 5 minutes. Exits (stop-loss, position-flip closes from `position_monitor.py`) must always pass `is_entry=False` and continue using `TRADE_ACTION_DEAL`.
- **Verification required before this is safe to ship:** confirm MT5 actually calls `oms_callback(..., status, ...)` with `OrderStatus.EXPIRED` when a pending order's broker-side expiration fires, *without* the bot needing to poll for it. If MT5 just silently removes the order with no callback, the risk-budget release path added this week (`on_order_update` in `scripts/run_gqos_live.py`, keyed on `OrderStatus.EXPIRED`) will never fire, reintroducing the same budget-leak class of bug that was just fixed. If MT5 doesn't push this, a polling check (`mt5.orders_get()` against pending tickets, comparing against `expiration`) needs to be added to the adapter.

---

## 3. Dynamic TP/SL (ML)

**Finding:** SL/TP is currently computed inline in `gqos/live/alpha_worker.py` (lines ~297–355) using a static `atr_sl_multiplier` from `config/symbols.yaml` × ATR. There is no `risk/sl_tp_calculator.py` in the live path (that name doesn't exist in this codebase) — the original plan's target was wrong.

**What needs to change:**
- New `ml/dynamic_targets.py`: RandomForest regressor(s) trained on `data/learning/live_outcomes.jsonl` (via `outcome_logger.get_outcomes_df()`), features = session, ATR, spread, pattern similarity; targets = realized MFE/MAE distance in price units.
- **Data volume check needed before training is meaningful** — `live_outcomes.jsonl` is a young, small file; if it doesn't have enough rows per symbol/session bucket, the model will overfit noise. Check row count per symbol before deciding whether to train per-symbol or pool across symbols.
- `gqos/live/alpha_worker.py` SL/TP block (~line 297–316): replace the static buffer calculation with a call into the trained model, but clamp the result: `sl_distance = clamp(model_sl, MIN_SL_DISTANCE, MAX_SL_DISTANCE)` and same for TP, where the min/max bounds are derived from the existing static ATR-multiplier calculation (e.g., 0.5x–2x of what the static formula would have produced) so a bad prediction can't create unbounded risk.
- Position sizing (`SizingStage`) depends on SL distance for fixed-risk sizing — confirm the dynamic SL is computed *before* `SizePositionCommand` is built, not after, so sizing uses the real (post-clamp) stop distance, not the old static one.

---

## Suggested sequencing

1. Promotion confirm-gate (#1) — smallest change, modifies existing flow, no new order-execution risk.
2. Smart Execution (#2) — verify the MT5 EXPIRED-callback behavior first (spike/test in isolation before touching the live adapter).
3. Dynamic TP/SL (#3) — largest effort; gate on the live-data volume check above.

No implementation has started. This document is the reference for when you're ready to proceed.
