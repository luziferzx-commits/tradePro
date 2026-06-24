"""journal/trade_journal.py"""
import os
import csv
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class TradeJournal:
    def __init__(self, signals_file="results/signals_journal.csv", trades_file="results/trade_journal.csv"):
        self.signals_file = signals_file
        self.trades_file = trades_file
        
        self.signals_headers = [
            "timestamp", "event_type", "symbol", "side", "status", "reason",
            "model_probability", "market_score", "expected_r", "spread_points",
            "liquidity_score", "final_score", "source"
        ]
        
        self.trades_headers = [
            "timestamp", "event_type", "symbol", "side", "status", "reason",
            "lot_size", "entry_price", "exit_price", "pnl", "r_multiple", "source"
        ]
        
        self._ensure_file(self.signals_file, self.signals_headers)
        self._ensure_file(self.trades_file, self.trades_headers)

    def _ensure_file(self, filepath: str, headers: list[str]):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        if not os.path.exists(filepath):
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)

    def log_signal(self, sig: dict, source: str = "MULTI_ASSET_SCANNER"):
        row = [
            sig.get("timestamp", datetime.now().isoformat()),
            "SIGNAL",
            sig.get("symbol", "UNKNOWN"),
            sig.get("side", "UNKNOWN"),
            sig.get("status", "UNKNOWN"),
            sig.get("reason", ""),
            f"{sig.get('model_probability', 0.0):.4f}",
            sig.get("market_score", 0),
            f"{sig.get('expected_r', 0.0):.2f}",
            sig.get("spread_points", 0),
            f"{sig.get('liquidity_score', 0.0):.2f}",
            f"{sig.get('final_score', 0.0):.2f}",
            source
        ]
        self._append(self.signals_file, row)
        
    def log_trade(self, trade: dict, source: str = "EXECUTION"):
        row = [
            trade.get("timestamp", datetime.now().isoformat()),
            "TRADE",
            trade.get("symbol", "UNKNOWN"),
            trade.get("side", "UNKNOWN"),
            trade.get("status", "CLOSED"),
            trade.get("reason", ""),
            trade.get("lot_size", 0.0),
            trade.get("entry_price", 0.0),
            trade.get("exit_price", 0.0),
            trade.get("pnl", 0.0),
            trade.get("r_multiple", 0.0),
            source
        ]
        self._append(self.trades_file, row)

    def _append(self, filepath: str, row: list):
        try:
            with open(filepath, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception as e:
            logger.error(f"Failed to write to journal {filepath}: {e}")
