import MetaTrader5 as mt5
mt5.initialize()
acc = mt5.account_info()
pos = mt5.positions_get() or []
print(f'Balance: {acc.balance:.2f}')
total_risk = 0
for p in pos:
    sl_dist = abs(p.price_open - p.sl) if p.sl > 0 else 0
    # Note: tick_value is usually $1 per point for indices/forex standard, but simplified here
    risk = sl_dist * p.volume * 100
    total_risk += risk
    dir_str = "BUY" if p.type==0 else "SELL"
    print(f'{p.symbol} | {dir_str} | Lot:{p.volume} | SL_dist:{sl_dist:.3f} | Risk:${risk:.0f} | PnL:{p.profit:.2f}')
print(f'Total Risk: ${total_risk:.0f} / Max: ${acc.balance * 0.06:.0f}')
