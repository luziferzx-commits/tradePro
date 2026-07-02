"""scripts/run_survivability_report.py — Generates Phase A.1 Survivability Report."""
import os
import sys
import logging
import numpy as np
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from risk.monte_carlo import MonteCarloSimulator
from risk.risk_of_ruin import RiskOfRuinCalculator
from risk.trade_history_loader import TradeHistoryLoader

logger = logging.getLogger("SurvivabilityReport")
logging.basicConfig(level=logging.INFO, format="%(message)s")

def simulate_scenario(returns: list[float], n_simulations: int, n_trades: int) -> dict:
    paths = MonteCarloSimulator.simulate(returns, n_simulations=n_simulations, n_trades=n_trades)
    drawdowns = MonteCarloSimulator.calculate_drawdowns(paths)
    
    return {
        "exp": np.mean(returns),
        "worst_dd": RiskOfRuinCalculator.expected_worst_case_drawdown(drawdowns, 95.0),
        "prob_10": RiskOfRuinCalculator.calculate_ruin_probability(drawdowns, 10.0),
        "prob_20": RiskOfRuinCalculator.calculate_ruin_probability(drawdowns, 20.0),
        "prob_30": RiskOfRuinCalculator.calculate_ruin_probability(drawdowns, 30.0),
        "prob_50": RiskOfRuinCalculator.calculate_ruin_probability(drawdowns, 50.0),
        "streak_prob": RiskOfRuinCalculator.calculate_loss_streak_probability(returns, 10, min(1000, n_simulations), n_trades)
    }

def format_scenario(name: str, metrics: dict) -> str:
    lines = [
        f"### {name}",
        f"- **Avg Expectancy**: {metrics['exp']:.2f}R",
        f"- **Expected 95th Percentile Max Drawdown**: {metrics['worst_dd']:.2f}R",
        f"- **Probability of 10R Drawdown**: {metrics['prob_10']:.2%}",
        f"- **Probability of 20R Drawdown**: {metrics['prob_20']:.2%}",
        f"- **Probability of 30R Drawdown**: {metrics['prob_30']:.2%}",
        f"- **Probability of 50R Drawdown (Ruin)**: {metrics['prob_50']:.2%}",
        f"- **Probability of 10 Consecutive Losses**: {metrics['streak_prob']:.2%}",
        ""
    ]
    return "\n".join(lines)

def generate_report():
    print("=" * 70)
    print(" GENERATING SURVIVABILITY REPORT (REAL VALIDATION) ")
    print("=" * 70)
    
    df, is_synthetic = TradeHistoryLoader.load_history()
    returns = df['r_multiple'].tolist()
    
    n_simulations = 10000
    n_trades = 250
    
    logger.info(f"Running Monte Carlo with {len(returns)} historical trades...")
    
    # Generate Scenarios
    scenarios = {}
    
    # 1. Base Case
    scenarios["Base Case"] = simulate_scenario(returns, n_simulations, n_trades)
    
    # 2. Slippage Shock
    r_slip = RiskOfRuinCalculator.apply_slippage_shock(returns, 0.1)
    scenarios["Slippage Shock (-0.1R)"] = simulate_scenario(r_slip, n_simulations, n_trades)
    
    # 3. Severe Slippage Shock
    r_sev = RiskOfRuinCalculator.apply_slippage_shock(returns, 0.25)
    scenarios["Severe Slippage Shock (-0.25R)"] = simulate_scenario(r_sev, n_simulations, n_trades)
    
    # 4. Bad Regime Shock
    r_bad = RiskOfRuinCalculator.apply_bad_regime_shock(returns, 0.20)
    scenarios["Bad Regime Shock (-20% WR)"] = simulate_scenario(r_bad, n_simulations, n_trades)
    
    # 5. Loss Streak Shock
    r_streak = RiskOfRuinCalculator.apply_loss_streak_shock(returns, 10)
    scenarios["Loss Streak Shock (+10 initial losses)"] = simulate_scenario(r_streak, n_simulations, n_trades)
    
    # 6. Worst-Case Bootstrap
    r_worst = RiskOfRuinCalculator.apply_worst_case_bootstrap(returns, 0.40)
    scenarios["Worst Regime Bootstrap (Bottom 40%)"] = simulate_scenario(r_worst, n_simulations, n_trades)
    
    # Verdict Logic
    base = scenarios["Base Case"]
    severe = scenarios["Severe Slippage Shock (-0.25R)"]
    
    base_passed = (base["prob_50"] < 0.05) and (base["exp"] >= 0.1)
    severe_survived = (severe["prob_50"] < 0.05)
    
    # Check if any shock failed
    any_shock_failed = False
    for name, s in scenarios.items():
        if name != "Base Case" and s["prob_50"] >= 0.05:
            any_shock_failed = True
            
    if not base_passed:
        verdict = "❌ FAIL (Base case failed minimum requirements)"
    elif severe_survived and not any_shock_failed:
        verdict = "✅ PASS (Robust against all stress tests)"
    else:
        verdict = "⚠️ CAUTION (Base passed, but vulnerable to specific shocks)"

    worst_case_dd = base["worst_dd"]
    recommended_risk_pct = 20.0 / worst_case_dd if worst_case_dd > 0 else 1.0
    recommended_risk_pct = min(max(recommended_risk_pct, 0.1), 2.0)
    
    report_lines = [
        "# Survivability & Risk of Ruin Report",
        f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ""
    ]
    
    if is_synthetic:
        report_lines.extend([
            "> [!WARNING]",
            "> **SYNTHETIC DATA USED**",
            "> No real trade history was found. This report uses a synthetic fallback dataset.",
            "> The metrics below are theoretical. Please run on real trade history before live deployment.",
            ""
        ])
    else:
        report_lines.extend([
            "> [!NOTE]",
            "> **REAL TRADE HISTORY USED**",
            f"> Sourced from: {df['source_file'].iloc[0]}",
            ""
        ])
        
    report_lines.extend([
        "## 1. System Metrics (Input)",
        f"- **Historical Trades Analyzed**: {len(returns)}",
        f"- **Data Source**: {df['source_file'].iloc[0]}",
        "",
        "## 2. Stress Test Results",
        ""
    ])
    
    for name, metrics in scenarios.items():
        report_lines.append(format_scenario(name, metrics))
        
    report_lines.extend([
        "## 3. Verdict & Recommendations",
        f"**SYSTEM VERDICT**: {verdict}",
        "",
        f"- **Recommended Risk Per Trade**: {recommended_risk_pct:.2f}% (Targeting <20% Account Drawdown on Base Case)",
        "- **Capital Suitability ($500 balance)**: ",
        f"  - Risking 1% per trade = $5 risk. Max Expected DD = ${worst_case_dd * 5:.2f} ({(worst_case_dd * 5 / 500):.1%} of balance).",
        "  - **Survival Probability**: " + ("Excellent" if (worst_case_dd * 5 / 500) < 0.5 else "Poor (High chance of margin call)"),
        ""
    ])
    
    report_content = "\n".join(report_lines)
    
    os.makedirs("reports", exist_ok=True)
    with open("reports/survivability_report.md", "w", encoding="utf-8") as f:
        f.write(report_content)
        
    logger.info("Report successfully generated: reports/survivability_report.md")
    print("\n" + report_content)

if __name__ == "__main__":
    generate_report()
