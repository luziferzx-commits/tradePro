import numpy as np
from scipy.optimize import minimize
from decimal import Decimal
from typing import List, Dict, Tuple, Any
from gqos.portfolio.optimization.interfaces import IOptimizer, IConstraint, IObjectiveFunction
from gqos.portfolio.optimization.models import OptimizationProblem, TargetPortfolio
from gqos.portfolio.optimization.constraints import MaxWeightConstraint, SumToOneConstraint, SectorWeightConstraint
from gqos.portfolio.optimization.objectives import MinimizeVarianceObjective, MaximizeSharpeObjective, EqualRiskContributionObjective
from gqos.portfolio.optimization.exceptions import OptimizationFailedError
from gqos.portfolio.optimization.validator import AllocationValidator

class BaseScipyOptimizer(IOptimizer):
    def __init__(self):
        self.validator = AllocationValidator()

    def _regularize_covariance(self, cov_matrix: np.ndarray, epsilon: float = 1e-8) -> np.ndarray:
        """
        Ensures the covariance matrix is Positive Semi-Definite.
        Adds a small ridge penalty (epsilon) to the diagonal if ill-conditioned or singular.
        """
        # Check eigenvalues
        eigvals = np.linalg.eigvalsh(cov_matrix)
        if np.any(eigvals < 0) or np.isclose(eigvals.min(), 0):
            # Regularize
            return cov_matrix + np.eye(cov_matrix.shape[0]) * epsilon
        return cov_matrix

    def _map_constraints(self, symbols: List[str], constraints: List[IConstraint]) -> Tuple[List[Tuple[float, float]], List[Dict[str, Any]]]:
        bounds = [(0.0, 1.0) for _ in symbols] # Default long-only
        scipy_constraints = []

        for constraint in constraints:
            if isinstance(constraint, MaxWeightConstraint):
                max_w = float(constraint._max_weight)
                bounds = [(0.0, max_w) for _ in symbols]
            elif isinstance(constraint, SumToOneConstraint):
                scipy_constraints.append({
                    'type': 'eq',
                    'fun': lambda w: np.sum(w) - 1.0
                })
            elif isinstance(constraint, SectorWeightConstraint):
                # Sector constraints are inequalities: max_weight - sum(weights in sector) >= 0
                max_w = float(constraint._max_sector_weight)
                
                # Group indices by sector
                sector_indices = {}
                for idx, sym in enumerate(symbols):
                    sec = constraint._symbol_to_sector.get(sym, "UNKNOWN")
                    if sec not in sector_indices:
                        sector_indices[sec] = []
                    sector_indices[sec].append(idx)
                    
                # Create a closure for each sector to capture the indices correctly
                for sec, indices in sector_indices.items():
                    def make_fun(idxs):
                        return lambda w: max_w - np.sum(w[idxs])
                    scipy_constraints.append({
                        'type': 'ineq',
                        'fun': make_fun(indices)
                    })
        
        return bounds, scipy_constraints

    def _extract_arrays(self, problem: OptimizationProblem) -> Tuple[List[str], np.ndarray, np.ndarray]:
        symbols = sorted(list(problem.expected_returns.keys()))
        n = len(symbols)
        
        mu = np.zeros(n)
        cov = np.zeros((n, n))
        
        for i, sym in enumerate(symbols):
            mu[i] = float(problem.expected_returns[sym])
            for j, sym2 in enumerate(symbols):
                cov[i, j] = float(problem.covariance_matrix[sym].get(sym2, Decimal('0')))
                
        return symbols, mu, self._regularize_covariance(cov)

class ScipyMeanVarianceOptimizer(BaseScipyOptimizer):
    def optimize(self, problem: OptimizationProblem, constraints: List[IConstraint], objective: IObjectiveFunction) -> TargetPortfolio:
        symbols, mu, cov = self._extract_arrays(problem)
        bounds, scipy_constraints = self._map_constraints(symbols, constraints)
        n = len(symbols)
        
        # Initial guess: Equal weight
        w0 = np.ones(n) / n
        
        if isinstance(objective, MinimizeVarianceObjective):
            def objective_fn(w):
                return 0.5 * np.dot(w.T, np.dot(cov, w))
        elif isinstance(objective, MaximizeSharpeObjective):
            rf = objective.risk_free_rate
            def objective_fn(w):
                ret = np.dot(w.T, mu) - rf
                vol = np.sqrt(np.dot(w.T, np.dot(cov, w)))
                # We minimize negative Sharpe
                return -(ret / vol) if vol > 1e-8 else 0
        else:
            raise OptimizationFailedError(f"Unsupported objective: {objective.name}")
            
        result = minimize(
            objective_fn, 
            w0, 
            method='SLSQP', 
            bounds=bounds, 
            constraints=scipy_constraints,
            tol=1e-6
        )
        
        if not result.success:
            raise OptimizationFailedError(f"Solver failed: {result.message}")
            
        # Extract weights and construct target portfolio
        target_weights = {sym: Decimal(str(round(result.x[i], 6))) for i, sym in enumerate(symbols)}
        target_portfolio = TargetPortfolio(target_weights)
        
        # Validation Gate
        self.validator.validate(target_portfolio, constraints)
        
        return target_portfolio

class ScipyRiskParityOptimizer(BaseScipyOptimizer):
    def optimize(self, problem: OptimizationProblem, constraints: List[IConstraint], objective: IObjectiveFunction) -> TargetPortfolio:
        if not isinstance(objective, EqualRiskContributionObjective):
            raise OptimizationFailedError(f"Unsupported objective: {objective.name}")
            
        symbols, mu, cov = self._extract_arrays(problem)
        bounds, scipy_constraints = self._map_constraints(symbols, constraints)
        n = len(symbols)
        
        # Initial guess: Equal weight
        w0 = np.ones(n) / n
        
        def objective_fn(w):
            # Marginal Risk Contribution (MRC)
            portfolio_variance = np.dot(w.T, np.dot(cov, w))
            if portfolio_variance < 1e-8:
                return 0
                
            mrc = np.dot(cov, w) / np.sqrt(portfolio_variance)
            # Risk Contribution (RC)
            rc = w * mrc
            
            # We want to minimize the sum of squared differences between all pairs of RC
            # Equivalently, minimize the variance of RC
            return np.sum((rc - np.mean(rc))**2)
            
        result = minimize(
            objective_fn, 
            w0, 
            method='SLSQP', 
            bounds=bounds, 
            constraints=scipy_constraints,
            tol=1e-8
        )
        
        if not result.success:
            raise OptimizationFailedError(f"Solver failed: {result.message}")
            
        # Extract weights and construct target portfolio
        target_weights = {sym: Decimal(str(round(result.x[i], 6))) for i, sym in enumerate(symbols)}
        target_portfolio = TargetPortfolio(target_weights)
        
        # Validation Gate
        self.validator.validate(target_portfolio, constraints)
        
        return target_portfolio
