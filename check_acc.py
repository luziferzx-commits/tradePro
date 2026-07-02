import MetaTrader5 as mt5
import yaml
import logging

logging.basicConfig(level=logging.INFO)

if not mt5.initialize():
    print("MT5 Init failed")
    exit()

acc = mt5.account_info()
print(f"Balance: {acc.balance}, Equity: {acc.equity}, Free Margin: {acc.margin_free}")

positions = mt5.positions_get()
for p in positions:
    print(f"Pos: {p.symbol} {p.volume} {p.type}")

mt5.shutdown()
