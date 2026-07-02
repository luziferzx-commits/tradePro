import os
import sys
import logging
import time
import threading
import json
import html
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import MetaTrader5 as mt5

from config.settings import settings

from gqos.messaging.bus import LocalCommandBus, LocalEventBus
from gqos.messaging.contracts import MessageEnvelope

from gqos.accounting.engine import AccountingEngine
from gqos.portfolio.manager import PortfolioManager
from gqos.risk.events import ExecuteTradeCommand
from gqos.common.enums import TradeDirection

from gqos.live.events import OrderStatus, OrderUpdateEvent, ReconciliationFillEvent, HeartbeatEvent
from gqos.live.oms import OrderManagementSystem
from gqos.live.adapters.mt5_adapter import MT5BrokerAdapter
from gqos.live.safety import GlobalKillSwitch, HeartbeatMonitor
from gqos.live.persistence import LedgerSnapshotService
from gqos.live.engine import LiveTradingEngine
from gqos.live.alpha_worker import AlphaWorker
from gqos.live.position_monitor import PositionMonitor
from gqos.live.daily_scheduler import DailyReportScheduler
from gqos.live.process_lock import SingleInstanceLock
from gqos.ops.live_guard import LiveSessionGuard, build_startup_summary, get_daily_pnl

from gqos.sizing.engine import PositionSizingEngine
from gqos.sizing.policies import FixedFractionalPolicy, FixedRiskPolicy, DynamicScalingPolicy
from gqos.sizing.events import SizePositionCommand

from gqos.risk.circuit_breaker import CircuitBreaker
from gqos.risk.exposure_engine import ExposureEngine
from gqos.risk.engine import RiskBudgetEngine, CircuitBreakerEngine
from gqos.risk.store import RiskBudgetStore
from gqos.risk.models import RiskBudget
from gqos.risk.assets import AssetDirectory, AssetMetadata
from gqos.risk.exposure import ExposureLimits

from gqos.execution.pipeline import TradingPipeline
from gqos.execution.stages import AccountLossGuardStage, TradeThrottleStage, SizingStage, CircuitBreakerStage, ExposureStage, RiskBudgetStage, PortfolioSnapshotStage, PortfolioReservationStage, ExecutionStage

# ─── Learning Loop imports ─────────────────────────────────────────
from gqos.learning.outcome_logger import outcome_logger
from gqos.learning.retrain_trigger import retrain_trigger
# ──────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("GQOS-Live")

class DefaultFeeModel:
    def calculate_fee(self, symbol, direction, quantity, execution_price):
        return Decimal('0'), "USD"

class DefaultFxConverter:
    def convert(self, amount, from_curr, to_curr):
        return amount

def start_outcome_sync_worker(stop_event: threading.Event):
    def _loop():
        while not stop_event.is_set():
            try:
                from gqos.learning.mt5_outcome_sync import (
                    enrich_existing_outcomes,
                    sync_mt5_closed_deals_today,
                    sync_mt5_open_positions_to_pending,
                )
                restored = sync_mt5_open_positions_to_pending()
                synced = sync_mt5_closed_deals_today()
                enriched = enrich_existing_outcomes()
                if restored:
                    logger.info("[Learning] Periodic MT5 outcome sync restored %s open positions.", restored)
                    logger.info("[Learning] Pending outcome cache reloaded: %s entries.", outcome_logger.reload_pending())
                if synced:
                    logger.info("[Learning] Periodic MT5 outcome sync backfilled %s deals.", synced)
                if enriched:
                    logger.info("[Learning] Periodic MT5 outcome sync enriched %s outcomes.", enriched)
            except Exception as e:
                logger.warning("[Learning] Periodic MT5 outcome sync failed: %s", e)
            stop_event.wait(300)

    thread = threading.Thread(target=_loop, name="MT5OutcomeSync", daemon=True)
    thread.start()
    return thread

def start_continuous_market_sim_worker(stop_event: threading.Event):
    def _loop():
        while not stop_event.is_set():
            try:
                from gqos.learning.continuous_market_simulator import continuous_market_simulator
                stats = continuous_market_simulator.scan_once()
                if any(stats.values()):
                    logger.info("[ContinuousMarketSim] %s", stats)
                    try:
                        from gqos.learning.simulation_analyzer import build_simulation_recommendations
                        recs = build_simulation_recommendations()
                        logger.info(
                            "[SimulationAnalyzer] recommendations=%s virtual=%s missed=%s",
                            len(recs.get("recommendations", {})),
                            recs.get("virtual_rows", 0),
                            recs.get("missed_rows", 0),
                        )
                    except Exception as analyzer_error:
                        logger.warning("[SimulationAnalyzer] failed: %s", analyzer_error)
            except Exception as e:
                logger.warning("[ContinuousMarketSim] worker failed: %s", e)
            stop_event.wait(60)

    thread = threading.Thread(target=_loop, name="ContinuousMarketSim", daemon=True)
    thread.start()
    return thread

def main():
    logger.info("=========================================")
    logger.info("  GQOS LIVE ENGINE (INSTITUTIONAL MODE)  ")
    logger.info("=========================================")
    outcome_sync_stop = threading.Event()
    market_sim_stop = threading.Event()

    instance_lock = SingleInstanceLock("GQOS Live Engine", settings.LIVE_ENGINE_LOCK_PORT)
    if not instance_lock.acquire():
        logger.critical("Another GQOS live engine instance is already active. Exiting.")
        return
    
    if not mt5.initialize():
        logger.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
        instance_lock.release()
        return
        
    acc_info = mt5.account_info()
    if not acc_info:
        logger.error("Could not retrieve MT5 account info.")
        instance_lock.release()
        return
        
    initial_capital = Decimal(str(acc_info.balance))
    logger.info(f"Connected to MT5. Initial Capital: ${initial_capital}")
    try:
        from gqos.learning.mt5_outcome_sync import (
            enrich_existing_outcomes,
            sync_mt5_closed_deals_today,
            sync_mt5_open_positions_to_pending,
        )
        restored = sync_mt5_open_positions_to_pending()
        synced = sync_mt5_closed_deals_today()
        enriched = enrich_existing_outcomes()
        if restored:
            logger.info("[Learning] Restored %s open MT5 positions into pending outcomes.", restored)
            logger.info("[Learning] Pending outcome cache reloaded: %s entries.", outcome_logger.reload_pending())
        if synced:
            logger.info("[Learning] Backfilled %s MT5 closed deals into live outcomes.", synced)
        if enriched:
            logger.info("[Learning] Enriched %s existing outcomes with pattern metadata.", enriched)
    except Exception as e:
        logger.warning("[Learning] MT5 outcome backfill skipped: %s", e)
    risk_reference_balance = Decimal(
        os.getenv("GQOS_RISK_REFERENCE_BALANCE", str(max(initial_capital, Decimal("10000"))))
    )
    max_realized_dd_pct = Decimal(os.getenv("GQOS_MAX_REALIZED_DD_PCT", "0.10"))
    max_equity_dd_pct = Decimal(os.getenv("GQOS_MAX_EQUITY_DD_PCT", "0.12"))
    logger.warning(
        "Account loss guard armed: reference=%s max_realized_dd=%.2f%% max_equity_dd=%.2f%%",
        risk_reference_balance,
        float(max_realized_dd_pct * 100),
        float(max_equity_dd_pct * 100),
    )

    cmd_bus = LocalCommandBus(logger)
    evt_bus = LocalEventBus(logger)
    
    accounting = AccountingEngine(evt_bus, DefaultFeeModel(), DefaultFxConverter())
    portfolio  = PortfolioManager("LivePort", initial_capital * 10)
    portfolio.allocate_capital("gqos_alpha_v1", initial_capital * 10)
    logger.info("Allocated virtual capital to strategies.")
    
    oms = OrderManagementSystem(evt_bus)
    
    def oms_callback(order_id, status, fill_qty, fill_price, msg):
        if status == "FILL":
            oms.apply_fill(order_id, fill_qty, fill_price, msg)
        else:
            oms.update_order_status(order_id, OrderStatus(status), msg)
            
    adapter    = MT5BrokerAdapter(evt_bus, oms_callback)
    safety     = GlobalKillSwitch(oms, adapter)
    hb_monitor = HeartbeatMonitor(evt_bus, safety, timeout_seconds=60.0)
    
    snapshot_path = "gqos_ledger_state.json"
    persistence   = LedgerSnapshotService(snapshot_path)
    
    live_engine = LiveTradingEngine(
        evt_bus, cmd_bus, oms, adapter, safety, persistence, accounting, portfolio
    )
    
    sizing_engine = PositionSizingEngine()
    policy        = DynamicScalingPolicy(base_risk_fraction=Decimal('0.005'))
    cb_engine     = CircuitBreakerEngine()

    try:
        import yaml as _yaml
        with open("config/symbols.yaml", "r") as _f:
            _symbol_aliases = _yaml.safe_load(_f).get("symbol_aliases", {})
    except Exception:
        _symbol_aliases = {}
    
    asset_dir = AssetDirectory()
    for sym in ["XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "US500",
                "EURUSD", "GBPUSD", "USDJPY", "NAS100", "GER40", "USTEC",
                "AUDUSD", "USDCAD", "USOIL", "XRPUSD", "SOLUSD",
                "US30", "NZDUSD", "EURGBP", "AUDCAD"]:
        asset_dir.register_asset(AssetMetadata(sym,       "MIXED", "FX", sym))
        asset_dir.register_asset(AssetMetadata(f"{sym}m", "MIXED", "FX", sym))
        asset_dir.register_asset(AssetMetadata(f"{sym}.m","MIXED", "FX", sym))
        broker_symbol = _symbol_aliases.get(sym)
        if broker_symbol:
            asset_dir.register_asset(AssetMetadata(broker_symbol, "MIXED", "FX", sym))
            
    exposure = ExposureEngine(asset_dir, ExposureLimits(
        max_gross_exposure=initial_capital * Decimal('20.0'),
        max_net_exposure=initial_capital * Decimal('10.0'),
        max_symbol_exposure=initial_capital * Decimal('5.0'),
        max_sector_exposure=initial_capital * Decimal('10.0'),
        max_correlation_group_exposure=initial_capital * Decimal('10.0')
    ))
    
    store = RiskBudgetStore()
    store.save(RiskBudget("gqos_alpha_v1", total_capacity=initial_capital * 20, utilized_capacity=Decimal('0')))
    risk_engine = RiskBudgetEngine(store)
    
    from gqos.risk.news_filter import NewsFilter
    from gqos.risk.news_stage import NewsGuardStage
    news_filter = NewsFilter(block_minutes=15)
    news_stage  = NewsGuardStage(news_filter)

    risk_budget_stage = RiskBudgetStage(risk_engine)
    portfolio_reservation_stage = PortfolioReservationStage(portfolio)
    trade_throttle_stage = TradeThrottleStage(
        max_global_per_hour=settings.TRADE_THROTTLE_MAX_GLOBAL_PER_HOUR,
        max_symbol_per_hour=settings.TRADE_THROTTLE_MAX_SYMBOL_PER_HOUR,
        state_file="data/execution/trade_throttle.json",
    )
    account_loss_guard_stage = AccountLossGuardStage(
        reference_balance=risk_reference_balance,
        max_realized_drawdown_pct=max_realized_dd_pct,
        max_equity_drawdown_pct=max_equity_dd_pct,
    )

    stages = [
        news_stage,
        account_loss_guard_stage,
        PortfolioSnapshotStage(portfolio),
        SizingStage(sizing_engine, policy),
        CircuitBreakerStage(cb_engine),
        ExposureStage(
            exposure,
            max_positions=settings.MAX_OPEN_POSITIONS,
            max_portfolio_risk_pct=0.08,
            max_correlated_positions_per_group=settings.MAX_CORRELATED_POSITIONS_PER_GROUP,
        ),
        trade_throttle_stage,
        risk_budget_stage,
        portfolio_reservation_stage,
        ExecutionStage(cmd_bus, portfolio)
    ]
    pipeline = TradingPipeline(stages, evt_bus)
    
    def handle_sizing_command(env: MessageEnvelope):
        result = pipeline.dispatch(env)
        logger.info(f"Pipeline Result: {result}")
        if isinstance(result, str) and result.startswith("Halted"):
            try:
                outcome_logger.discard_intent_by_symbol(env.payload.symbol)
            except Exception as e:
                logger.error(f"[Learning] Failed to discard intent on halt for {getattr(env.payload, 'symbol', '?')}: {e}")
            if "Halted at RiskBudgetStage" in result or "Halted at ExecutionStage" in result:
                trade_throttle_stage.release_for_symbol(env.payload.symbol, result)
        
    cmd_bus.register_handler(SizePositionCommand, handle_sizing_command)
    
    alpha_worker = AlphaWorker(cmd_bus)
    session_guard = LiveSessionGuard(alpha_worker=alpha_worker, circuit_breaker=cb_engine)
    # Let the AlphaWorker loop auto-clear daily guard pauses at day rollover.
    alpha_worker._guard_reevaluate = session_guard.reevaluate
    startup_guard_reason = session_guard.enforce_startup_limits(float(initial_capital))

    # ─── Dynamic Position Management ──────────────────────────────
    from strategy.indicators import IndicatorCalculator
    position_monitor = PositionMonitor(
        evidence_router=alpha_worker.evidence_router,
        mt5_client=alpha_worker.mt5_client,
        indicator_calculator=IndicatorCalculator,
        magic_number=settings.MAGIC_NUMBER,
        reduce_threshold=0.50,     # REDUCE เมื่อ edge เหลือ < 50%
        flip_confirm_candles=1,    # รอ 1 candle confirm ก่อน FLIP
        news_filter=news_filter    # Pass news filter for active management
    )
    position_monitor.set_cmd_bus(cmd_bus)
    position_monitor.set_event_bus(evt_bus)
    
    alpha_worker.position_monitor = position_monitor
    
    # ─── Daily Report Scheduler ───────────────────────────────────
    scheduler = DailyReportScheduler(report_hour_utc=8)
    scheduler.start()
    outcome_sync_thread = start_outcome_sync_worker(outcome_sync_stop)
    market_sim_thread = start_continuous_market_sim_worker(market_sim_stop)
    # ──────────────────────────────────────────────────────────────
    
    logger.info("Dynamic Position Management started.")
    # ──────────────────────────────────────────────────────────────

    # ─── Retrain Callback: reload ML model หลัง retrain เสร็จ ────────
    def on_retrain_complete():
        logger.info("♻️  Reloading ML models after retrain...")
        try:
            alpha_worker.predictor.reload()
            logger.info("✅ ML models reloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to reload ML models: {e}")

    retrain_trigger.on_retrain_complete = on_retrain_complete
    retrain_trigger.trigger_if_due()
    logger.info(
        f"Learning Loop armed. "
        f"Retrain trigger: every {retrain_trigger.retrain_threshold} live trades."
    )
    # ────────────────────────────────────────────────────────────────

    from notifications.telegram_notifier import notify_trade_executed, notify_trade_closed, send_telegram
    from database.logger import DatabaseLogger
    import uuid
    from datetime import datetime

    telegram_alert_state_path = os.getenv(
        "GQOS_TELEGRAM_ALERT_STATE_PATH",
        os.path.join("data", "learning", "telegram_alert_state.json"),
    )
    telegram_alert_lock = threading.Lock()

    def _load_telegram_alert_state():
        state = {"opened": set(), "closed": set()}
        try:
            with open(telegram_alert_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                state["opened"].update(str(x) for x in data.get("opened", []))
                state["closed"].update(str(x) for x in data.get("closed", []))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"[Telegram] Could not load alert state: {e}")
        try:
            emitted_path = os.getenv(
                "GQOS_EMITTED_CLOSE_STORE",
                os.path.join("data", "learning", "emitted_close_deals.json"),
            )
            with open(emitted_path, "r", encoding="utf-8") as f:
                emitted = json.load(f)
            if isinstance(emitted, list):
                state["closed"].update(str(x) for x in emitted)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"[Telegram] Could not seed closed alert state: {e}")
        return state

    telegram_alert_state = _load_telegram_alert_state()

    def _save_telegram_alert_state():
        try:
            directory = os.path.dirname(telegram_alert_state_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            payload = {
                "opened": sorted(telegram_alert_state["opened"])[-5000:],
                "closed": sorted(telegram_alert_state["closed"])[-5000:],
            }
            with open(telegram_alert_state_path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
        except Exception as e:
            logger.warning(f"[Telegram] Could not save alert state: {e}")

    def _telegram_alert_seen(kind: str, key: str) -> bool:
        if not key:
            return False
        with telegram_alert_lock:
            return str(key) in telegram_alert_state[kind]

    def _remember_telegram_alert(kind: str, key: str):
        if not key:
            return
        with telegram_alert_lock:
            telegram_alert_state[kind].add(str(key))
            _save_telegram_alert_state()

    def _position_side_text(pos) -> str:
        pos_type = getattr(pos, "type", None)
        if pos_type == mt5.POSITION_TYPE_BUY:
            return "BUY"
        if pos_type == mt5.POSITION_TYPE_SELL:
            return "SELL"
        return "UNKNOWN"

    def notify_resumed_existing_positions() -> None:
        try:
            positions = list(mt5.positions_get() or [])
        except Exception as e:
            logger.warning(f"[Telegram] Could not load existing positions for resume alert: {e}")
            return
        if not positions:
            return

        lines = [
            "<b>GQOS Existing Positions Resumed</b>",
            "These positions were already open before this restart.",
            "The bot will manage them; later close alerts are expected.",
            "",
        ]
        for pos in positions[:12]:
            ticket = str(getattr(pos, "ticket", "UNKNOWN"))
            symbol = html.escape(str(getattr(pos, "symbol", "UNKNOWN")))
            side = _position_side_text(pos)
            volume = float(getattr(pos, "volume", 0.0) or 0.0)
            price_open = float(getattr(pos, "price_open", 0.0) or 0.0)
            profit = float(getattr(pos, "profit", 0.0) or 0.0)
            lines.append(
                f"{symbol} #{ticket} {side} lot={volume:.2f} "
                f"entry={price_open:.5f} float={profit:+.2f}"
            )
        if len(positions) > 12:
            lines.append(f"...and {len(positions) - 12} more")

        if send_telegram("\n".join(lines)):
            for pos in positions:
                ticket = str(getattr(pos, "ticket", "") or "")
                if ticket:
                    _remember_telegram_alert("opened", ticket)
            logger.info("[Telegram] Resumed existing positions alert sent: %s positions", len(positions))
        else:
            logger.warning("[Telegram] Resumed existing positions alert failed")
    
    def on_trade_executed(env: MessageEnvelope):
        cmd = env.payload
        ticket_val = getattr(cmd, 'ticket', None)
        ticket_str = str(ticket_val) if ticket_val else "GQOS"
        open_key = ticket_str if ticket_str and ticket_str != "GQOS" else f"{cmd.symbol}:{cmd.direction}:{cmd.execution_price}:{cmd.quantity}"
        logger.info(
            "[Telegram] Trade open event received: symbol=%s direction=%s ticket=%s lot=%s price=%s",
            cmd.symbol,
            cmd.direction,
            ticket_str,
            cmd.quantity,
            cmd.execution_price,
        )
        # NOTE: The TRADE OPENED Telegram alert is now sent by PositionMonitor,
        # which polls MT5 positions every cycle (reliable), because this
        # TradeExecutedEvent path fired inconsistently. Kept here for DB logging.
        # Log to Database
        try:
            db_ticket = str(ticket_val) if ticket_val else str(uuid.uuid4())
            DatabaseLogger.log_trade_execution(
                signal_id=None,
                ticket=db_ticket,
                symbol=cmd.symbol,
                direction=cmd.direction.name if hasattr(cmd.direction, 'name') else str(cmd.direction),
                volume=float(cmd.quantity),
                open_price=float(cmd.execution_price),
                sl=float(getattr(cmd, "stop_loss", None) or 0.0),
                tp=float(getattr(cmd, "take_profit", None) or 0.0),
                open_time=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Failed to log trade execution to DB: {e}")
        
    last_closed_dir   = {}
    processed_realized_close_keys = set(telegram_alert_state["closed"])

    def _clean_trade_direction(direction):
        text = getattr(direction, "name", direction)
        text = str(text or "UNKNOWN").upper()
        if "BUY" in text or "LONG" in text:
            return "BUY"
        if "SELL" in text or "SHORT" in text:
            return "SELL"
        return "UNKNOWN"

    def _position_direction_from_mt5_close(ticket):
        if not ticket:
            return "UNKNOWN"
        try:
            from execution.mt5_direction import closing_deal_position_direction
            deals = mt5.history_deals_get(position=int(ticket)) or []
            close_deals = [
                d for d in deals
                if getattr(d, "entry", None) == mt5.DEAL_ENTRY_OUT
            ]
            if not close_deals:
                return "UNKNOWN"
            close_deal = close_deals[-1]
            return closing_deal_position_direction(getattr(close_deal, "type", None))
        except Exception as e:
            logger.warning(f"[Telegram] Could not derive close direction for ticket={ticket}: {e}")
            return "UNKNOWN"

    def _actual_r_from_mt5_history(ticket, realized_pnl: float):
        if not ticket or not str(ticket).isdigit():
            return None

        def _deal_side(deal) -> str:
            deal_type = getattr(deal, "type", None)
            if deal_type == mt5.DEAL_TYPE_BUY:
                return "BUY"
            if deal_type == mt5.DEAL_TYPE_SELL:
                return "SELL"
            return "UNKNOWN"

        def _pending_meta_for_history(symbol: str, side: str, entry_price: float):
            try:
                pending_path = os.getenv(
                    "GQOS_PENDING_TRADES_PATH",
                    os.path.join("data", "learning", "pending_trades.json"),
                )
                with open(pending_path, "r", encoding="utf-8") as f:
                    pending = json.load(f)
            except Exception:
                return None

            best_meta = None
            best_score = None
            for meta in pending.values() if isinstance(pending, dict) else []:
                if not isinstance(meta, dict):
                    continue
                if str(meta.get("symbol") or "") != symbol:
                    continue
                if _clean_trade_direction(meta.get("direction")) != side:
                    continue
                try:
                    meta_entry = float(meta.get("fill_price") or meta.get("actual_entry_price") or meta.get("entry_price") or 0.0)
                    meta_sl = float(meta.get("stop_loss_price") or meta.get("sl_price") or 0.0)
                except Exception:
                    continue
                if meta_entry <= 0 or meta_sl <= 0:
                    continue

                sl_dist = abs(meta_entry - meta_sl)
                entry_diff = abs(entry_price - meta_entry)
                tolerance = max(sl_dist * 0.35, abs(entry_price) * 0.005)
                if entry_diff > tolerance:
                    continue

                score = entry_diff / max(sl_dist, 1e-12)
                if best_score is None or score < best_score:
                    best_score = score
                    best_meta = meta
            return best_meta

        try:
            position_id = int(ticket)
            deals = list(mt5.history_deals_get(position=position_id) or [])
            if not deals:
                return None

            open_deals = [d for d in deals if getattr(d, "entry", None) == mt5.DEAL_ENTRY_IN]
            close_deals = [d for d in deals if getattr(d, "entry", None) == mt5.DEAL_ENTRY_OUT]
            if not open_deals:
                return None

            open_deal = open_deals[0]
            close_deal = close_deals[-1] if close_deals else None
            symbol = str(getattr(open_deal, "symbol", "") or getattr(close_deal, "symbol", "") or "")
            entry_price = float(getattr(open_deal, "price", 0.0) or 0.0)
            volume = float(
                getattr(close_deal, "volume", 0.0)
                if close_deal is not None
                else getattr(open_deal, "volume", 0.0)
                or 0.0
            )
            if entry_price <= 0 or volume <= 0 or not symbol:
                return None
            side = _deal_side(open_deal)

            sl_price = 0.0
            try:
                orders = list(mt5.history_orders_get(position=position_id) or [])
            except Exception:
                orders = []
            for order in orders:
                candidate = float(getattr(order, "sl", 0.0) or 0.0)
                if candidate > 0:
                    sl_price = candidate
                    break
            if sl_price <= 0:
                meta = _pending_meta_for_history(symbol, side, entry_price)
                if meta:
                    sl_price = float(meta.get("stop_loss_price") or meta.get("sl_price") or 0.0)
                    logger.info(
                        "[Telegram] Matched pending metadata for close R: ticket=%s decision=%s symbol=%s side=%s",
                        ticket,
                        meta.get("decision_id"),
                        symbol,
                        side,
                    )
            if sl_price <= 0:
                return None

            info = mt5.symbol_info(symbol)
            if info is None:
                return None
            tick_size = float(getattr(info, "trade_tick_size", 0.0) or getattr(info, "point", 0.0) or 0.0)
            tick_value = float(getattr(info, "trade_tick_value", 0.0) or 0.0)
            sl_dist = abs(entry_price - sl_price)
            if tick_size <= 0 or tick_value <= 0 or sl_dist <= 0:
                return None

            risk_amount = (sl_dist / tick_size) * tick_value * volume
            if risk_amount <= 0:
                return None
            return round(float(realized_pnl) / risk_amount, 3)
        except Exception as e:
            logger.warning(f"[Telegram] Could not calculate R from MT5 history for ticket={ticket}: {e}")
            return None

    def on_position_closed(env: MessageEnvelope):
        cmd = env.payload
        last_closed_dir[cmd.symbol] = _clean_trade_direction(cmd.direction)
        pos_key = f"{cmd.strategy_id}_{cmd.symbol}"
        if pos_key in accounting.state.positions:
            logger.info(
                f"[Portfolio/RiskBudget] {cmd.symbol} partial close detected; "
                "keeping reservation until the position is fully closed."
            )
            return

        try:
            risk_budget_stage.release_for_symbol(cmd.symbol)
        except Exception as e:
            logger.error(f"[RiskBudget] Failed to release allocation for {cmd.symbol}: {e}")
        try:
            release_event = portfolio_reservation_stage.release_event_for_symbol(
                cmd.symbol,
                "Position Closed",
            )
            if release_event:
                evt_bus.publish(MessageEnvelope.create(
                    release_event,
                    version=env.version,
                    correlation_id=env.correlation_id,
                    trace_id=env.trace_id,
                    run_id=env.run_id,
                    sequence_number=env.sequence_number,
                ))
        except Exception as e:
            logger.error(f"[Portfolio] Failed to release cash reservation for {cmd.symbol}: {e}")

    _TERMINAL_NO_FILL_STATUSES = (OrderStatus.REJECTED, OrderStatus.CANCELLED, OrderStatus.EXPIRED)

    def on_order_update(env: MessageEnvelope):
        evt = env.payload
        if evt.status in _TERMINAL_NO_FILL_STATUSES and evt.filled_quantity == Decimal('0'):
            try:
                if getattr(evt, "risk_allocation_id", ""):
                    released = risk_budget_stage.release_for_allocation_id(evt.risk_allocation_id)
                else:
                    released = risk_budget_stage.release_for_symbol(evt.symbol)

                if getattr(evt, "portfolio_allocation_id", ""):
                    release_event = portfolio_reservation_stage.release_event_for_allocation_id(
                        evt.portfolio_allocation_id,
                        f"Order {evt.status.value} Without Fill: {evt.message}",
                    )
                else:
                    release_event = portfolio_reservation_stage.release_event_for_symbol(
                        evt.symbol,
                        f"Order {evt.status.value} Without Fill: {evt.message}",
                    )
                if released:
                    logger.info(
                        f"[RiskBudget] Released allocation for {evt.symbol} "
                        f"after order reached {evt.status.value} ({evt.message})"
                    )
                if release_event:
                    evt_bus.publish(MessageEnvelope.create(
                        release_event,
                        version=env.version,
                        correlation_id=env.correlation_id,
                        trace_id=env.trace_id,
                        run_id=env.run_id,
                        sequence_number=env.sequence_number,
                    ))
                outcome_logger.discard_intent_by_symbol(evt.symbol)
                trade_throttle_stage.release_for_symbol(evt.symbol, f"Order {evt.status.value} without fill")
            except Exception as e:
                logger.error(f"[RiskBudget/Learning] Failed to release allocation/intent for {evt.symbol} on {evt.status.value}: {e}")
        elif evt.status in _TERMINAL_NO_FILL_STATUSES:
            logger.info(
                f"[Portfolio/RiskBudget] {evt.symbol} reached {evt.status.value} "
                f"with filled_quantity={evt.filled_quantity}; keeping reservation "
                "until the resulting position is fully closed."
            )

    def on_portfolio_reject(env: MessageEnvelope):
        evt = env.payload
        try:
            risk_budget_stage.release_for_symbol(evt.symbol)
            outcome_logger.discard_intent_by_symbol(evt.symbol)
            trade_throttle_stage.release_for_symbol(evt.symbol, "Portfolio Reservation rejection")
            logger.info(
                f"[RiskBudget/Learning] Released allocation + discarded intent "
                f"for {evt.symbol} after Portfolio Reservation rejection."
            )
        except Exception as e:
            logger.error(f"[RiskBudget/Learning] Failed to release/discard for {evt.symbol}: {e}")
        
    def on_realized_pnl(env: MessageEnvelope):
        cmd       = env.payload
        ticket    = getattr(cmd, 'ticket', None)
        exit_price = float(getattr(cmd, 'exit_price', 0.0))
        close_key = str(ticket) if ticket else f"{cmd.symbol}:{cmd.realized_pnl}:{exit_price}"
        if close_key in processed_realized_close_keys or _telegram_alert_seen("closed", close_key):
            logger.warning(
                f"[Learning/Telegram] Duplicate realized close event skipped: "
                f"{cmd.symbol} ticket={ticket} pnl={cmd.realized_pnl}"
            )
            return
        processed_realized_close_keys.add(close_key)

        acc       = mt5.account_info()
        balance   = acc.balance if acc else 0.0
        
        # Use direction from event if available (from retrospective catch-up), else fallback
        evt_direction = getattr(cmd, "direction", None)
        direction = _clean_trade_direction(evt_direction)
        if direction == "UNKNOWN":
            direction = _position_direction_from_mt5_close(ticket)
        if direction == "UNKNOWN":
            direction = last_closed_dir.get(cmd.symbol, "UNKNOWN")

        # Log to Database
        try:
            if ticket:
                DatabaseLogger.log_trade_close(
                    ticket=ticket,
                    close_price=exit_price,
                    close_time=datetime.utcnow(),
                    pnl=float(cmd.realized_pnl)
                )
        except Exception as e:
            logger.error(f"Failed to log trade close to DB: {e}")

        # ─── Learning Loop: บันทึก outcome ───────────────────────────
        record = None
        try:
            if ticket and str(ticket).isdigit():
                record = outcome_logger.on_trade_closed(
                    ticket=int(ticket),
                    realized_pnl=float(cmd.realized_pnl),
                    exit_price=exit_price,
                )
            else:
                record = outcome_logger.on_trade_closed_by_symbol(
                    symbol=cmd.symbol,
                    realized_pnl=float(cmd.realized_pnl),
                    exit_price=exit_price,
                )
            if record:
                outcome = "WIN" if float(cmd.realized_pnl) > 0 else "LOSS"
                retrain_trigger.on_trade_closed(
                    outcome=outcome,
                    symbol=cmd.symbol,
                    realized_pnl=float(cmd.realized_pnl),
                )
                stats = outcome_logger.get_stats()
                logger.info(
                    f"[Learning] {cmd.symbol} {outcome} pnl={cmd.realized_pnl:.2f} | "
                    f"Live stats: {stats['total']} trades "
                    f"WR={stats['win_rate']}% PnL={stats['total_pnl']:.2f}"
                )
        except Exception as e:
            logger.warning(f"[Learning] on_trade_closed failed: {e}")

        rr = None
        duration_seconds = getattr(cmd, "duration_seconds", None)
        if record:
            try:
                actual_r = record.get("actual_r")
                rr = float(actual_r) if actual_r is not None else None
            except Exception:
                rr = None
            
            try:
                if duration_seconds is None and record.get("open_time") and record.get("close_time"):
                    from datetime import datetime
                    open_t = datetime.fromisoformat(record["open_time"])
                    close_t = datetime.fromisoformat(record["close_time"])
                    duration_seconds = (close_t - open_t).total_seconds()
            except Exception:
                pass
                
            record_direction = _clean_trade_direction(record.get("direction"))
            if record_direction != "UNKNOWN":
                direction = record_direction
        if rr is None:
            rr = _actual_r_from_mt5_history(ticket, float(cmd.realized_pnl))
            if rr is not None:
                logger.info(f"[Telegram] Calculated close R from MT5 history: ticket={ticket} R={rr:+.3f}")

        sent = notify_trade_closed(
            ticket=str(ticket) if ticket else "UNKNOWN",
            symbol=cmd.symbol,
            direction=direction,
            profit=float(cmd.realized_pnl),
            rr=rr,
            balance=float(balance),
            duration_seconds=duration_seconds
        )
        if sent:
            _remember_telegram_alert("closed", close_key)
        else:
            logger.warning(f"[Telegram] Trade close alert failed: {cmd.symbol} ticket={ticket}")
        # ─────────────────────────────────────────────────────────────

        try:
            equity = float(getattr(acc, "equity", balance)) if acc else None
            guard_reason = session_guard.record_closed_trade(
                symbol=cmd.symbol,
                pnl=float(cmd.realized_pnl),
                balance=float(balance),
                equity=equity,
            )
            if guard_reason:
                logger.warning("[LiveGuard] %s", guard_reason)
                send_telegram(
                    f"<b>GQOS Live Guard</b>\n{guard_reason}\n"
                    "Existing positions will still be managed."
                )
        except Exception as e:
            logger.warning(f"[LiveGuard] failed to evaluate close event: {e}")

        # ─── Daily Loss Circuit Breaker ──────────────────────────────
        try:
            if balance > 0:
                daily_pnl, _, _, _ = get_daily_pnl()
                max_loss = balance * -settings.MAX_DAILY_LOSS_PCT
                if daily_pnl < max_loss:
                    logger.critical(f"Circuit Breaker TRIPPED! Daily Loss {daily_pnl:.2f} exceeded limit {max_loss:.2f}")
                    cb_engine.trip("DAILY_LOSS_LIMIT", f"Exceeded daily drawdown limit: {daily_pnl:.2f}")
        except Exception as e:
            logger.error(f"Failed to check daily loss circuit breaker: {e}")
        # ─────────────────────────────────────────────────────────────
        
    from gqos.risk.events import TradeExecutedEvent
    from gqos.accounting.events import PositionClosedEvent, RealizedPnLEmittedEvent
    from gqos.portfolio.events import TradeRejectedByPortfolioEvent
    
    evt_bus.subscribe(TradeExecutedEvent,     on_trade_executed)
    evt_bus.subscribe(PositionClosedEvent,    on_position_closed)
    evt_bus.subscribe(RealizedPnLEmittedEvent, on_realized_pnl)
    evt_bus.subscribe(OrderUpdateEvent,       on_order_update)
    evt_bus.subscribe(TradeRejectedByPortfolioEvent, on_portfolio_reject)
    
    from notifications.telegram_listener import TelegramCommandListener
    
    def shutdown_bot():
        import os
        logger.warning("🚨 EMERGENCY SHUTDOWN INITIATED")
        os._exit(0)
        
    cmd_listener = TelegramCommandListener(alpha_worker=alpha_worker, shutdown_callback=shutdown_bot)
    cmd_listener.start()

    live_engine.start()
    send_telegram(build_startup_summary())
    notify_resumed_existing_positions()
    if startup_guard_reason:
        logger.warning("[LiveGuard] %s", startup_guard_reason)
        send_telegram(
            f"<b>GQOS Startup Guard</b>\n{startup_guard_reason}\n"
            "Existing positions will still be managed."
        )
    position_monitor.start()
    alpha_worker.start()
    
    logger.info("GQOS Live Engine is completely booted and running. Press Ctrl+C to exit.")

    restart_flag = os.getenv("GQOS_RESTART_FLAG", os.path.join("data", "execution", "restart.flag"))
    try:
        while True:
            time.sleep(1)
            # Restart trigger: a supervisor can relaunch us after a structural
            # config change (e.g. symbol enable/disable) without touching the
            # terminal — just drop the flag file and we exit gracefully.
            if os.path.exists(restart_flag):
                logger.warning("[Restart] flag detected — restarting engine (supervisor will relaunch).")
                try:
                    os.remove(restart_flag)
                except OSError:
                    pass
                raise KeyboardInterrupt
    except KeyboardInterrupt:
        logger.info("Shutting down GQOS...")
        scheduler.stop()
        outcome_sync_stop.set()
        market_sim_stop.set()
        outcome_sync_thread.join(timeout=2)
        market_sim_thread.join(timeout=2)
        position_monitor.stop()
        alpha_worker.stop()
        live_engine.stop()
        outcome_sync_stop.set()
        market_sim_stop.set()
        mt5.shutdown()
        instance_lock.release()
        logger.info("Shutdown complete.")
    finally:
        instance_lock.release()

if __name__ == "__main__":
    main()
