"""risk/risk_of_ruin.py — Calculate statistical risk metrics."""
import numpy as np

class RiskOfRuinCalculator:
    @staticmethod
    def calculate_ruin_probability(max_drawdowns: np.ndarray, ruin_threshold: float) -> float:
        """Calculates the probability of hitting or exceeding the ruin threshold."""
        if len(max_drawdowns) == 0:
            return 0.0
        ruined_paths = np.sum(max_drawdowns >= ruin_threshold)
        return float(ruined_paths / len(max_drawdowns))

    @staticmethod
    def calculate_drawdown_probabilities(max_drawdowns: np.ndarray, thresholds: list[float]) -> dict[float, float]:
        """Calculates the probability of exceeding specific drawdown thresholds."""
        probs = {}
        for t in thresholds:
            probs[t] = RiskOfRuinCalculator.calculate_ruin_probability(max_drawdowns, t)
        return probs

    @staticmethod
    def expected_worst_case_drawdown(max_drawdowns: np.ndarray, percentile: float = 95.0) -> float:
        """Calculates the expected worst-case drawdown at a given confidence percentile."""
        if len(max_drawdowns) == 0:
            return 0.0
        return float(np.percentile(max_drawdowns, percentile))

    @staticmethod
    def calculate_loss_streak_probability(trade_returns: list[float], streak_length: int, n_simulations: int = 10000, n_trades: int = 250) -> float:
        """Calculates the probability of encountering a loss streak of at least `streak_length`."""
        if not trade_returns or streak_length <= 0:
            return 0.0
            
        returns_array = np.array(trade_returns)
        is_loss = (returns_array < 0).astype(int)
        
        samples = np.random.choice(is_loss, size=(n_simulations, n_trades), replace=True)
        
        padded_samples = np.hstack([np.zeros((n_simulations, 1)), samples])
        cumsum = np.cumsum(padded_samples, axis=1)
        rolling_sums = cumsum[:, streak_length:] - cumsum[:, :-streak_length]
        
        has_streak = np.any(rolling_sums == streak_length, axis=1)
        return float(np.sum(has_streak) / n_simulations)

    @staticmethod
    def apply_slippage_shock(trade_returns: list[float], shock_amount: float) -> list[float]:
        """Subtracts a fixed amount (e.g. 0.1R) from every trade."""
        return [r - shock_amount for r in trade_returns]

    @staticmethod
    def apply_bad_regime_shock(trade_returns: list[float], penalty_prob: float = 0.20) -> list[float]:
        """Flips winners to losers with probability penalty_prob."""
        shocked = []
        for r in trade_returns:
            if r > 0 and np.random.rand() < penalty_prob:
                shocked.append(-1.0)
            else:
                shocked.append(r)
        return shocked
        
    @staticmethod
    def apply_loss_streak_shock(trade_returns: list[float], inject_streak_length: int = 10) -> list[float]:
        """Injects a streak of consecutive losses at the beginning."""
        shocked = list(trade_returns)
        return [-1.0] * inject_streak_length + shocked

    @staticmethod
    def apply_worst_case_bootstrap(trade_returns: list[float], bottom_percentile: float = 0.40) -> list[float]:
        """Returns only the bottom X% of the trade returns, sorted."""
        if not trade_returns:
            return []
        arr = np.sort(trade_returns)
        cutoff = max(1, int(len(arr) * bottom_percentile))
        return arr[:cutoff].tolist()
