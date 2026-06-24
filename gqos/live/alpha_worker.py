import logging
import threading
import time
from typing import Optional
from decimal import Decimal
import MetaTrader5 as mt5

from gqos.messaging.bus import ICommandBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.common.enums import TradeDirection
from gqos.sizing.events import SizePositionCommand

from market.symbol_registry import SymbolRegistry
from market.market_metadata import MarketMetadata
from scanner.multi_asset_scanner import MultiAssetScanner
from ml.predictor import MLPredictor
from data.mt5_client import MT5Client

logger = logging.getLogger(__name__)

class AlphaWorker:
    """
    Background worker that runs the Alpha Generation (Scanner + Predictor) loop
    and pushes Trade Intent commands to the GQOS Event Bus.
    """
    def __init__(self, cmd_bus: ICommandBus):
        self._cmd_bus = cmd_bus
        self._running = False
        self._thread = None
        
        # Initialize legacy components required for Alpha Generation
        self.registry = SymbolRegistry("config/symbols.yaml")
        self.metadata = MarketMetadata(self.registry)
        self.mt5_client = MT5Client()
        self.predictor = MLPredictor()
        
        self.scanner = MultiAssetScanner(self.registry, self.metadata, self.mt5_client, self.predictor)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("AlphaWorker started.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        logger.info("AlphaWorker stopped.")

    def _run_loop(self):
        while self._running:
            try:
                # Wait for new candle (using the robust mt5_client method)
                # Since we're in a separate thread, we can block here.
                # However, to allow clean shutdown, we sleep in small increments.
                if not self.mt5_client.is_new_candle():
                    time.sleep(1)
                    continue

                logger.info("AlphaWorker: New closed candle detected. Scanning markets...")
                
                approved, rejected = self.scanner.scan_all()
                
                logger.info(f"AlphaWorker: Scan complete. {len(approved)} signals approved. Sleeping 60s...")
                for sig in approved:
                    symbol = sig['symbol']
                    side = sig['side']
                    direction = TradeDirection.BUY if side == "BUY" else TradeDirection.SELL
                    
                    # Fetch current price for entry_price
                    sym_info = mt5.symbol_info(symbol)
                    if not sym_info:
                        logger.error(f"Could not get symbol info for {symbol}")
                        continue
                        
                    entry_price = Decimal(str(sym_info.ask if direction == TradeDirection.BUY else sym_info.bid))
                    conviction = Decimal(str(sig.get('model_probability', 0.5)))
                    
                    cmd = SizePositionCommand(
                        strategy_id="gqos_alpha_v1",
                        symbol=symbol,
                        direction=direction,
                        entry_price=entry_price,
                        stop_loss_price=None, # Will be calculated by sizing/risk if needed
                        conviction=conviction,
                        metrics=None,
                        volatility=None
                    )
                    
                    logger.info(f"AlphaWorker: Emitting SizePositionCommand for {symbol} {direction.name}")
                    self._cmd_bus.dispatch(MessageEnvelope.create(payload=cmd, version=1))
                
                # Sleep to prevent tight loop since is_new_candle returns True
                # Break it down so we can shut down quickly if Ctrl+C is pressed
                for _ in range(60):
                    if not self._running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in AlphaWorker loop: {e}")
                time.sleep(5)
