"""scripts/run_portfolio_simulation.py"""
import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from market.symbol_registry import SymbolRegistry
from market.market_metadata import MarketMetadata
from portfolio.correlation_engine import CorrelationEngine
from portfolio.exposure_manager import ExposureManager
from portfolio.capital_allocator import CapitalAllocator
from portfolio.portfolio_var import PortfolioVaR

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("PortfolioSim")

def run_simulation():
    print("=" * 70)
    print(" PORTFOLIO RISK ENGINE SIMULATION (HARDENED) ")
    print("=" * 70)
    
    registry = SymbolRegistry("config/symbols.yaml")
    metadata = MarketMetadata(registry)
    correlation = CorrelationEngine("config/correlations.yaml", metadata)
    exposure = ExposureManager(metadata, max_total_risk_pct=0.03, max_asset_class_risk_pct=0.02)
    allocator = CapitalAllocator(metadata, correlation, exposure, base_risk_pct=0.01, account_balance=1000.0)
    
    open_positions = [
        {"symbol": "GER40", "side": "BUY", "risk_amount_pct": 0.01, "risk_amount": 10.0} 
    ]
    
    print("\nCURRENT OPEN POSITIONS:")
    for pos in open_positions:
        print(f"[{pos['symbol']}] {pos['side']} | Risk: {pos['risk_amount_pct']:.2%}")
        
    var_result = PortfolioVaR.calculate_var(open_positions, correlation.correlations)
    print(f"\nCurrent Portfolio VaR/CVaR (95%):")
    print(f"- Method: {var_result['method']}")
    for w in var_result['warnings']:
        print(f"  [WARNING] {w}")
    print(f"- VaR: ${var_result['var']:.2f}")
    print(f"- CVaR: ${var_result['cvar']:.2f}")
    
    ranked_opportunities = [
        {"symbol": "US500", "side": "BUY", "final_score": 90.0, "model_probability": 0.9},
        {"symbol": "NAS100", "side": "BUY", "final_score": 85.0, "model_probability": 0.85},
        {"symbol": "BTCUSD", "side": "SELL", "final_score": 80.0, "model_probability": 0.8},
        {"symbol": "EURUSD", "side": "BUY", "final_score": 70.0, "model_probability": 0.7}
    ]
    
    print("\nALLOCATING CAPITAL & CHECKING EXPOSURE...")
    executions, rejections = allocator.allocate(ranked_opportunities, open_positions)
    
    print(f"\n✅ APPROVED FOR EXECUTION ({len(executions)}):")
    for ex in executions:
        red_text = ""
        if ex['reduction_reasons']:
            red_text = " | " + ", ".join(ex['reduction_reasons'])
        print(f"[{ex['symbol']}] {ex['side']} | Risk: {ex['risk_amount_pct']:.4%} | Est. Lot: {ex['estimated_lot']:.2f}{red_text}")
        open_positions.append({
            "symbol": ex['symbol'],
            "side": ex['side'],
            "risk_amount_pct": ex['risk_amount_pct'],
            "risk_amount": ex['risk_amount_pct'] * allocator.account_balance
        })
        
    print(f"\n❌ REJECTED BY PORTFOLIO ENGINE ({len(rejections)}):")
    for rej in rejections:
        print(f"[{rej['symbol']}] {rej['side']} | Reason: {rej['reject_reason']}")
        
    print("\nFINAL PORTFOLIO RISK REPORT:")
    
    var_result_new = PortfolioVaR.calculate_var(open_positions, correlation.correlations)
    print(f"- Method: {var_result_new['method']}")
    print(f"- New Portfolio VaR: ${var_result_new['var']:.2f}")
    print(f"- New Portfolio CVaR: ${var_result_new['cvar']:.2f}")
    
    total_risk = sum(pos['risk_amount_pct'] for pos in open_positions)
    print(f"- Total Open Risk: {total_risk:.2%}")
    
    classes = {}
    for pos in open_positions:
        c = metadata.get_asset_class(pos['symbol'])
        classes[c] = classes.get(c, 0.0) + pos['risk_amount_pct']
    for c, r in classes.items():
        print(f"  - {c}: {r:.2%}")
        
    print("=" * 70)

if __name__ == "__main__":
    run_simulation()
