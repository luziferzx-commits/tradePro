# tradePro (GoldGpt / GQOS)
*Alpha is temporary. The Pipeline is permanent.*

tradePro is an institutional-grade Quantitative Research Operating System designed to outlive any individual strategy. It is built to safely discover, validate, deploy, monitor, and manage autonomous trading strategies (like GoldBot) using rigorous walk-forward validation and Shadow Trading modes.

## Current Project Status
The project is currently undergoing a massive 9-Phase refactoring and stabilization sprint to transition from research code to a production-ready institutional framework. We are currently executing **Phase 1**.

### The 9-Phase Roadmap
1. **PHASE 1 — Repo Audit & Cleanup:** Fixing imports, standardizing configuration (`.env.example`), and ensuring `pytest --collect-only` passes with 0 errors.
2. **PHASE 2 — Safety & Risk Engine:** Implementing strict hard stops, Circuit Breakers, and position sizing guardrails.
3. **PHASE 3 — Backtest Integrity:** Removing Lookahead Bias, Data Leakage, and preventing overfitted models.
4. **PHASE 4 — ML Validation:** Stabilizing XGBoost / Random Forest models with proper Walk-Forward optimization.
5. **PHASE 5 — Multi-Market Support:** Expanding beyond XAUUSD using the edge discovered in Phase B1.
6. **PHASE 6 — Signal Quality Filter:** Hardening trade entries with advanced filters (e.g. Gemini LLM verification).
7. **PHASE 7 — Shadow Trading System:** Perfecting the Dry-Run environment to simulate live execution without financial risk.
8. **PHASE 8 — Test Suite:** Expanding test coverage and adding E2E Smoke Tests.
9. **PHASE 9 — Final Integration:** Full system audit and promotion to production.

## Architecture
- **Core Engine**: Deterministic `EventBus`, `Command` pattern, and plugin registry.
- **Execution**: `MetaTrader 5` adapter factory supporting both Live and Shadow execution modes.
- **Risk & Accounting**: Real-time Exposure Engine, Circuit Breakers, and Ledger.
- **Research / Memory**: `MarketMemoryV2` contextual observer and XGBoost predictor.

## Quick Start (Shadow Trading Mode)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/organization/tradePro.git
   cd tradePro
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Copy `.env.example` to `.env` and fill in your MT5 demo credentials.
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Run Shadow Validation:**
   ```bash
   # Make sure DRY_RUN and SHADOW_MODE are True in .env
   python -m scripts.run_shadow_validation
   ```

## Development and Testing
Always run the test suite after making changes to ensure you haven't broken the risk or execution engines.
```bash
pytest
```
