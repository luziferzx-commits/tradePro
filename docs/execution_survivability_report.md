# Execution Survivability Report (Phase B)

This report demonstrates the decay of theoretical alpha when subjected to realistic retail/VPS execution physics (Slippage, Spread, Latency, Partial Fills).

| Symbol | Base Edge (bps) | Fill Ratio | Latency (ms) | Slippage (bps) | Spread (bps) | Net PnL (bps) | Verdict |
|--------|-----------------|------------|--------------|----------------|--------------|---------------|---------|
| EURUSDm | 24.4 | 100% | 179 | 0.0 | 0.5 | **+22.6** | SURVIVED |
| GBPUSDm | 23.2 | 100% | 126 | 0.0 | 1.0 | **+21.4** | SURVIVED |
| XAUUSDm | 26.0 | 100% | 199 | 3.5 | 2.5 | **+18.5** | SURVIVED |
| BTCUSDm | 28.0 | 12% | 294 | 1125.0 | 15.0 | **-1139.0** | REJECTED (NEGATIVE EV) |
| US30m | 25.6 | 100% | 256 | 216.0 | 3.0 | **-195.5** | REJECTED (NEGATIVE EV) |