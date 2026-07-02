from collections import deque

from gqos.risk.portfolio_budget import PortfolioBudgetManager


class BudgetWithoutMt5(PortfolioBudgetManager):
    def _load_stats_from_mt5(self):
        return None


def test_portfolio_budget_pauses_symbol_after_material_realized_loss():
    budget = BudgetWithoutMt5()
    budget.stats["XAUUSDm"] = {
        "w": 1,
        "l": 3,
        "pnl": -250.0,
        "recent": deque([40.0, -90.0, -100.0, -100.0], maxlen=5),
    }

    assert budget.get_multiplier("XAUUSDm") == 0.0


def test_portfolio_budget_pauses_symbol_after_three_recent_losses():
    budget = BudgetWithoutMt5()
    budget.stats["USDJPYm"] = {
        "w": 3,
        "l": 3,
        "pnl": -50.0,
        "recent": deque([30.0, -20.0, -10.0, -15.0], maxlen=5),
    }

    assert budget.get_multiplier("USDJPYm") == 0.0


def test_portfolio_budget_pauses_low_win_rate_earlier_than_old_20_trade_rule():
    budget = BudgetWithoutMt5()
    budget.stats["USTECm"] = {
        "w": 1,
        "l": 4,
        "pnl": -80.0,
        "recent": deque([25.0, -30.0, -20.0, 10.0, -65.0], maxlen=5),
    }

    assert budget.get_multiplier("USTECm") == 0.0


def test_portfolio_budget_keeps_normal_symbol_active():
    budget = BudgetWithoutMt5()
    budget.stats["EURUSDm"] = {
        "w": 3,
        "l": 2,
        "pnl": 15.0,
        "recent": deque([20.0, -5.0, 10.0, -8.0, -2.0], maxlen=5),
    }

    assert budget.get_multiplier("EURUSDm") == 1.0
