import MetaTrader5 as mt5
mt5.initialize()
acc = mt5.account_info()
pos = mt5.positions_get() or []
print(f'Balance: {acc.balance:.2f}')
print(f'Open positions: {len(pos)}')
for p in pos:
    dir_str = "BUY" if p.type==0 else "SELL"
    print(f'{p.symbol} | {dir_str} | Entry:{p.price_open:.5f} | SL:{p.sl:.5f} | PnL:{p.profit:.2f}')
