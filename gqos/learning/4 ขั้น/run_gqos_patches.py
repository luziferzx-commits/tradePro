"""
Patches สำหรับ run_gqos_live.py และ alpha_worker.py
Copy-paste ตามที่ระบุด้านล่าง
"""

# ═══════════════════════════════════════════════════════════════
# PATCH A — gqos/live/alpha_worker.py
# ส่ง pattern metadata ผ่าน SizePositionCommand
# ═══════════════════════════════════════════════════════════════
PATCH_A = """
# หาบรรทัดที่สร้าง SizePositionCommand แล้วแก้เป็น:

cmd = SizePositionCommand(
    strategy_id="gqos_alpha_v1",
    symbol=symbol,
    direction=direction,
    entry_price=entry_price,
    stop_loss_price=sl_price,
    take_profit_price=(entry_price + sl_buffer * 2
                       if direction == TradeDirection.BUY
                       else entry_price - sl_buffer * 2),
    conviction=conviction,
    metrics=None,      # StrategyMetrics ยังไม่ได้ใช้
    volatility=None
)

# และก่อน dispatch cmd เพิ่มบรรทัดนี้ เพื่อบันทึก pattern metadata:
from gqos.learning.outcome_logger import outcome_logger
outcome_logger.on_trade_opened(
    symbol=symbol,
    direction=direction.name if hasattr(direction, 'name') else str(direction),
    entry_price=float(entry_price),
    sl_price=float(sl_price),
    tp_price=float(cmd.take_profit_price) if cmd.take_profit_price else 0.0,
    pattern_id=sig.get('metadata', {}).get('pattern_id') if sig.get('metadata') else None,
    pattern_pf=sig.get('metadata', {}).get('historical_pf', 0.0) if sig.get('metadata') else 0.0,
    pattern_sim=sig.get('metadata', {}).get('similarity_score', 0.0) if sig.get('metadata') else 0.0,
    session=SessionDetector.detect(datetime.utcnow().timestamp()) if True else 'Unknown',
    strategy_id="gqos_alpha_v1",
)
"""

# ═══════════════════════════════════════════════════════════════
# PATCH B — scripts/run_gqos_live.py
# Wire learning loop เข้า event bus
# เพิ่มหลัง notify_bot_started() บรรทัดประมาณ section "Setup Notifications"
# ═══════════════════════════════════════════════════════════════
PATCH_B = """
# เพิ่ม imports ตอนต้นไฟล์:
from gqos.learning.outcome_logger import outcome_logger
from gqos.learning.retrain_trigger import retrain_trigger

# ─── Learning Loop ─────────────────────────────────────────────
from gqos.accounting.events import PositionClosedEvent, RealizedPnLEmittedEvent

def on_position_closed_learning(env: MessageEnvelope):
    cmd = env.payload
    # บันทึก exit price ไว้ใช้คำนวณ R
    # PositionClosedEvent: symbol, exit_price, direction, quantity_closed
    symbol = cmd.symbol
    exit_price = float(cmd.exit_price) if hasattr(cmd, 'exit_price') else 0.0
    # เก็บ exit_price ชั่วคราวใน pending
    if symbol in outcome_logger._pending:
        outcome_logger._pending[symbol]['_exit_price'] = exit_price

def on_realized_pnl_learning(env: MessageEnvelope):
    cmd = env.payload
    # RealizedPnLEmittedEvent: strategy_id, symbol, realized_pnl
    exit_price = outcome_logger._pending.get(cmd.symbol, {}).get('_exit_price', 0.0)
    record = outcome_logger.on_trade_closed(
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

evt_bus.subscribe(PositionClosedEvent, on_position_closed_learning)
evt_bus.subscribe(RealizedPnLEmittedEvent, on_realized_pnl_learning)
# ──────────────────────────────────────────────────────────────
"""

print("Patches ready.")
print("Apply PATCH_A to: gqos/live/alpha_worker.py")
print("Apply PATCH_B to: scripts/run_gqos_live.py")
