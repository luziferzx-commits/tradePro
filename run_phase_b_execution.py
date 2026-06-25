import os
from datetime import datetime
from execution.paper_executor import PaperExecutor

def run_phase_b():
    print("=========================================")
    print(" PHASE B: Paper Execution Simulation     ")
    print("=========================================")
    
    executor = PaperExecutor()
    
    # Mocking ranked signals from the Multi-Market Scanner
    signals = [
        {
            "symbol": "EURUSDm",
            "direction": "BUY",
            "ml_prob": 0.61,
            "market_score": 0.9,
            "regime": "TRENDING",
            "atr": 0.0080,
            "spread": 0.5,
            "volatility_factor": 1.0,
            "entry_price": 1.1000,
            "signal_timestamp": datetime.now()
        },
        {
            "symbol": "GBPUSDm",
            "direction": "SELL",
            "ml_prob": 0.58,
            "market_score": 0.8,
            "regime": "RANGING",
            "atr": 0.0100,
            "spread": 1.0,
            "volatility_factor": 1.2,
            "entry_price": 1.2500,
            "signal_timestamp": datetime.now()
        },
        {
            "symbol": "XAUUSDm",
            "direction": "BUY",
            "ml_prob": 0.65,
            "market_score": 0.85,
            "regime": "TRENDING",
            "atr": 15.0,
            "spread": 2.5,
            "volatility_factor": 1.3,
            "entry_price": 2300.0,
            "signal_timestamp": datetime.now()
        },
        {
            "symbol": "BTCUSDm",
            "direction": "SELL",
            "ml_prob": 0.70, # High probability!
            "market_score": 0.95,
            "regime": "RANGING",
            "atr": 1500.0,
            "spread": 15.0,
            "volatility_factor": 2.5, # Very noisy
            "entry_price": 65000.0,
            "signal_timestamp": datetime.now()
        },
        {
            "symbol": "US30m",
            "direction": "BUY",
            "ml_prob": 0.64,
            "market_score": 0.8,
            "regime": "TRENDING",
            "atr": 400.0,
            "spread": 3.0,
            "volatility_factor": 1.8,
            "entry_price": 38000.0,
            "signal_timestamp": datetime.now()
        }
    ]
    
    report_lines = ["# Execution Survivability Report (Phase B)", ""]
    report_lines.append("This report demonstrates the decay of theoretical alpha when subjected to realistic retail/VPS execution physics (Slippage, Spread, Latency, Partial Fills).")
    report_lines.append("")
    report_lines.append("| Symbol | Base Edge (bps) | Fill Ratio | Latency (ms) | Slippage (bps) | Spread (bps) | Net PnL (bps) | Verdict |")
    report_lines.append("|--------|-----------------|------------|--------------|----------------|--------------|---------------|---------|")
    
    print("\nExecuting Ranked Signals in PAPER MODE...\n")
    
    for signal in signals:
        result = executor.execute_order(signal)
        
        # Format for display
        sym = result['symbol']
        edge = result['base_edge_bps']
        fill = result['fill_ratio'] * 100
        lat = result['latency_ms']
        slip = result['slippage_cost_bps']
        spr = result['spread_cost_bps']
        net = result['net_expectancy_bps']
        verdict = result['verdict']
        
        print(f" {sym} -> Net: {net:+.2f} bps | Fill: {fill:.0f}% | Latency: {lat:.0f}ms | Verdict: {verdict}")
        
        report_lines.append(f"| {sym} | {edge:.1f} | {fill:.0f}% | {lat:.0f} | {slip:.1f} | {spr:.1f} | **{net:+.1f}** | {verdict} |")
        
    print("\nPhase B Execution Physics Simulation Complete.")
    
    # Ensure docs directory exists
    os.makedirs("docs", exist_ok=True)
    with open("docs/execution_survivability_report.md", "w", encoding='utf-8') as f:
        f.write("\n".join(report_lines))
    print("Generated: docs/execution_survivability_report.md")

if __name__ == "__main__":
    os.environ['PYTHONPATH'] = "."
    run_phase_b()
