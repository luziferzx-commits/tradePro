"""
gqos/learning/__init__.py + wiring guide

วิธีเชื่อม Self-Learning Loop เข้ากับระบบที่มีอยู่

3 สิ่งที่ต้องแก้:
1. alpha_worker.py  → ส่ง pattern_id ผ่าน SizePositionCommand.metrics
2. run_gqos_live.py → subscribe events + wire learning components
3. mt5_adapter.py   → แจ้ง outcome_logger เมื่อ position ปิด
"""

# ──────────────────────────────────────────────────────────────────────────────
# PATCH 1: gqos/live/alpha_worker.py
# เพิ่ม pattern_id เข้าไปใน SizePositionCommand.metrics
# ──────────────────────────────────────────────────────────────────────────────
ALPHA_WORKER_PATCH = """
# ใน _run_loop ของ AlphaWorker หลังจากได้ sig จาก EvidenceRouter

# เดิม:
cmd = SizePositionCommand(
    strategy_id="gqos_alpha_v1",
    symbol=symbol,
    direction=direction,
    entry_price=entry_price,
    stop_loss_price=sl_price,
    conviction=conviction,
    metrics=sig.get('metrics'),       # ← pattern_id ไม่ได้ส่งไป
    volatility=sig.get('volatility')
)

# แก้เป็น:
cmd = SizePositionCommand(
    strategy_id="gqos_alpha_v1",
    symbol=symbol,
    direction=direction,
    entry_price=entry_price,
    stop_loss_price=sl_price,
    conviction=conviction,
    metrics={
        "pattern_id":         sig.get('metadata', {}).get('pattern_id'),
        "pattern_pf":         sig.get('metadata', {}).get('historical_pf', 0.0),
        "pattern_similarity": sig.get('metadata', {}).get('similarity_score', 0.0),
        "session":            sig.get('metadata', {}).get('session_label', 'Unknown'),
    },
    volatility=sig.get('volatility')
)
"""

# ──────────────────────────────────────────────────────────────────────────────
# PATCH 2: run_gqos_live.py
# เพิ่ม learning components เข้า event bus
# ──────────────────────────────────────────────────────────────────────────────
RUN_GQOS_PATCH = """
# เพิ่ม imports ตอนต้นไฟล์:
from gqos.learning.outcome_logger import outcome_logger
from gqos.learning.retrain_trigger import retrain_trigger

# เพิ่มหลังจาก setup Notifications (บรรทัดที่ subscribe TradeExecutedEvent):

# ─── Learning Loop Wiring ───────────────────────────────────────────
def on_trade_executed_learning(env: MessageEnvelope):
    cmd = env.payload
    # บันทึกตอนเปิด position
    outcome_logger.on_trade_opened(
        ticket=cmd.order_id,
        symbol=cmd.symbol,
        direction=cmd.direction.name if hasattr(cmd.direction, 'name') else str(cmd.direction),
        entry_price=float(cmd.execution_price),
        sl_price=float(cmd.stop_loss) if cmd.stop_loss else 0.0,
        tp_price=float(cmd.take_profit) if cmd.take_profit else 0.0,
        pattern_id=getattr(cmd, 'metadata', {}).get('pattern_id') if hasattr(cmd, 'metadata') else None,
        pattern_pf=getattr(cmd, 'metadata', {}).get('pattern_pf', 0.0) if hasattr(cmd, 'metadata') else 0.0,
        pattern_sim=getattr(cmd, 'metadata', {}).get('pattern_similarity', 0.0) if hasattr(cmd, 'metadata') else 0.0,
        session=getattr(cmd, 'metadata', {}).get('session', 'Unknown') if hasattr(cmd, 'metadata') else 'Unknown',
        strategy_id=cmd.strategy_id,
    )

def on_realized_pnl_learning(env: MessageEnvelope):
    cmd = env.payload
    # บันทึกตอนปิด position
    outcome_logger.on_trade_closed(
        ticket=str(cmd.order_id) if hasattr(cmd, 'order_id') else cmd.symbol,
        close_price=float(cmd.execution_price) if hasattr(cmd, 'execution_price') else 0.0,
        realized_pnl=float(cmd.realized_pnl),
    )
    # แจ้ง retrain trigger
    outcome = "WIN" if float(cmd.realized_pnl) > 0 else "LOSS"
    retrain_trigger.on_trade_closed(
        outcome=outcome,
        symbol=cmd.symbol,
        realized_pnl=float(cmd.realized_pnl),
    )

from gqos.risk.events import TradeExecutedEvent
from gqos.accounting.events import RealizedPnLEmittedEvent

evt_bus.subscribe(TradeExecutedEvent, on_trade_executed_learning)
evt_bus.subscribe(RealizedPnLEmittedEvent, on_realized_pnl_learning)
# ────────────────────────────────────────────────────────────────────
"""

# ──────────────────────────────────────────────────────────────────────────────
# PATCH 3: MLPredictor reload callback
# ──────────────────────────────────────────────────────────────────────────────
PREDICTOR_RELOAD_PATCH = """
# ใน run_gqos_live.py หลังจาก init predictor:

from gqos.learning.retrain_trigger import AutoRetrainTrigger

def on_retrain_complete():
    # Reload ML models หลัง retrain เสร็จ
    logger.info("♻️  Reloading ML models after retrain...")
    try:
        alpha_worker.predictor.reload()
        logger.info("✅ ML models reloaded successfully.")
    except Exception as e:
        logger.error(f"Failed to reload ML models: {e}")

# ตอน init retrain_trigger ให้ส่ง callback:
from gqos.learning.retrain_trigger import retrain_trigger
retrain_trigger.on_retrain_complete = on_retrain_complete
"""

print("Learning system wiring guide loaded.")
print("Apply ALPHA_WORKER_PATCH, RUN_GQOS_PATCH, PREDICTOR_RELOAD_PATCH")
print("to complete the Self-Learning Loop.")
