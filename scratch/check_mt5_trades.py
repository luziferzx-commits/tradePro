import MetaTrader5 as mt5
from datetime import datetime, timedelta

def main():
    if not mt5.initialize():
        print("Failed to initialize MT5")
        return
        
    print("=== Current Open Positions ===")
    positions = mt5.positions_get()
    if positions:
        for p in positions:
            print(f"Ticket: {p.ticket}, Symbol: {p.symbol}, Type: {p.type}, Volume: {p.volume}, Magic: {p.magic}, Comment: {p.comment}")
    else:
        print("No open positions.")
        
    print("\n=== Recent Deals (Last 7 Days) ===")
    now = datetime.now()
    deals = mt5.history_deals_get(now - timedelta(days=7), now)
    if deals:
        for d in deals[-20:]: # Show last 20 deals
            date = datetime.fromtimestamp(d.time).strftime('%Y-%m-%d %H:%M:%S')
            print(f"Date: {date}, Ticket: {d.ticket}, Order: {d.order}, Symbol: {d.symbol}, Volume: {d.volume}, Magic: {d.magic}, Comment: {d.comment}")
    else:
        print("No recent deals found.")
        
    mt5.shutdown()

if __name__ == '__main__':
    main()
