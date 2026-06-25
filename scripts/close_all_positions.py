import os
import sys
import MetaTrader5 as mt5

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.settings import settings

def main():
    if not mt5.initialize():
        print("initialize() failed")
        return
        
    positions = mt5.positions_get()
    if positions is None or len(positions) == 0:
        print("No open positions found.")
        mt5.shutdown()
        return

    print(f"Found {len(positions)} open positions. Closing them all...")
    
    for pos in positions:
        tick = mt5.symbol_info_tick(pos.symbol)
        if pos.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
            
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": order_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 20,
            "magic": pos.magic,
            "comment": "Auto-close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Failed to close {pos.symbol} ticket={pos.ticket}: {result.comment}")
        else:
            print(f"Successfully closed {pos.symbol} ticket={pos.ticket}")
            
    mt5.shutdown()

if __name__ == "__main__":
    main()
