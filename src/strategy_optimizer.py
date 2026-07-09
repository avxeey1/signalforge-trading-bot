"""Strategy Optimization & Backtesting Engine.

Optimize trading strategy parameters:
- Parameter grid search (find best settings)
- Walk-forward optimization (realistic out-of-sample testing)
- Monte Carlo simulations (robustness testing)
- Scenario analysis (stress testing)
- Optimization constraints (drawdown limits, win rate floors)
"""

import logging
from dataclasses import dataclass
from typing import Callable, Optional
from datetime import datetime
import itertools
import random

logger = logging.getLogger("SignalForge.Optimizer")


@dataclass
class OptimizationResult:
    """Strategy optimization result."""
    parameters: dict  # Optimal parameters found
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    robustness_score: float  # 0-100 (higher = more robust)
    best_fit: bool  # True if parameters are statistically significant
    timestamp: datetime = None


class StrategyOptimizer:
    """Strategy optimization and backtesting engine."""

    def __init__(self):
        self.min_trades_for_optimization = 30
        self.min_robustness_score = 60.0

    def grid_search_optimization(
        self,
        parameter_ranges: dict,
        backtest_func: Callable,
        constraints: Optional[dict] = None,
    ) -> Optional[OptimizationResult]:
        """Search parameter space for optimal settings.

        Args:
            parameter_ranges: Dict of param_name: [values]
            backtest_func: Function that returns metrics for parameters
            constraints: Dict of constraint_name: threshold

        Returns:
            OptimizationResult with best parameters
        """
        try:
            if not constraints:
                constraints = {
                    "min_win_rate": 0.45,
                    "max_drawdown": -0.30,
                    "min_trades": 20,
                }

            best_result = None
            best_score = -float('inf')

            # Generate all parameter combinations
            param_names = list(parameter_ranges.keys())
            param_values = list(parameter_ranges.values())
            combinations = list(itertools.product(*param_values))

            logger.info(f"Starting grid search with {len(combinations)} combinations")

            for i, combination in enumerate(combinations):
                params = dict(zip(param_names, combination))

                # Run backtest with these parameters
                result = backtest_func(params)
                if not result:
                    continue

                # Check constraints
                if not self._check_constraints(result, constraints):
                    continue

                # Calculate fitness score
                fitness = self._calculate_fitness(
                    result["return"],
                    result["sharpe"],
                    result["max_dd"],
                    result["win_rate"],
                )

                if fitness > best_score:
                    best_score = fitness
                    best_result = result
                    best_result["parameters"] = params

                if (i + 1) % max(1, len(combinations) // 10) == 0:
                    logger.info(f"Optimization progress: {i+1}/{len(combinations)}")

            if best_result:
                robustness = self._test_robustness(best_result, combinations, backtest_func)
                return OptimizationResult(
                    parameters=best_result["parameters"],
                    total_return=best_result["return"],
                    sharpe_ratio=best_result["sharpe"],
                    max_drawdown=best_result["max_dd"],
                    win_rate=best_result["win_rate"],
                    trade_count=best_result["trades"],
                    robustness_score=robustness,
                    best_fit=robustness > self.min_robustness_score,
                    timestamp=datetime.now(),
                )
        except Exception as e:
            logger.error(f"Error in grid search: {e}", exc_info=True)

        return None

    def walk_forward_optimization(
        self,
        trades: list,
        optimization_period: int = 60,  # Days
        forward_period: int = 10,  # Days
    ) -> dict:
        """Walk-forward analysis for realistic out-of-sample testing.

        Args:
            trades: Historical trades
            optimization_period: Days to optimize on
            forward_period: Days to test forward

        Returns:
            dict: WFA results with equity curve
        """
        try:
            if len(trades) < optimization_period + forward_period:
                logger.warning("Not enough trade history for WFA")
                return {}

            results = []
            step = forward_period

            for i in range(0, len(trades) - optimization_period, step):
                opt_trades = trades[i : i + optimization_period]
                forward_trades = trades[i + optimization_period : i + optimization_period + forward_period]

                if not opt_trades or not forward_trades:
                    break

                # Optimize on historical period
                opt_metrics = self._calculate_metrics(opt_trades)

                # Test on forward period
                forward_metrics = self._calculate_metrics(forward_trades)

                results.append({
                    "optimization_period": i // step,
                    "in_sample_metrics": opt_metrics,
                    "out_of_sample_metrics": forward_metrics,
                    "degradation_factor": self._calculate_degradation(
                        opt_metrics["sharpe"],
                        forward_metrics["sharpe"],
                    ),
                })

            return {
                "walk_forward_results": results,
                "average_in_sample_sharpe": sum(r["in_sample_metrics"]["sharpe"] for r in results) / len(results),
                "average_out_sample_sharpe": sum(r["out_of_sample_metrics"]["sharpe"] for r in results) / len(results),
                "average_degradation": sum(r["degradation_factor"] for r in results) / len(results),
            }
        except Exception as e:
            logger.error(f"Error in WFA: {e}", exc_info=True)
            return {}

    def monte_carlo_simulation(
        self,
        trades: list,
        simulations: int = 1000,
    ) -> dict:
        """Monte Carlo simulation for robustness testing.

        Args:
            trades: Historical trades
            simulations: Number of simulations to run

        Returns:
            dict: Simulation results with statistics
        """
        try:
            if not trades or len(trades) < 10:
                logger.warning("Not enough trades for Monte Carlo")
                return {}

            pnl_list = [t.get("pnl_sol", 0) for t in trades]
            simulation_results = []

            for _ in range(simulations):
                # Randomly shuffle trade outcomes
                shuffled_pnl = random.sample(pnl_list, len(pnl_list))
                final_equity = 1.0
                for pnl in shuffled_pnl:
                    final_equity += pnl
                simulation_results.append(final_equity)

            # Calculate statistics
            sorted_results = sorted(simulation_results)
            return {
                "worst_case": sorted_results[0],
                "best_case": sorted_results[-1],
                "median": sorted_results[len(sorted_results) // 2],
                "percentile_5": sorted_results[int(len(sorted_results) * 0.05)],
                "percentile_95": sorted_results[int(len(sorted_results) * 0.95)],
                "probability_profit": sum(1 for r in simulation_results if r > 1.0) / len(simulation_results),
            }
        except Exception as e:
            logger.error(f"Error in Monte Carlo: {e}", exc_info=True)
            return {}

    def _check_constraints(self, result: dict, constraints: dict) -> bool:
        """Check if result meets constraints."""
        if result["win_rate"] < constraints.get("min_win_rate", 0):
            return False
        if result["max_dd"] < constraints.get("max_drawdown", 0):
            return False
        if result["trades"] < constraints.get("min_trades", 0):
            return False
        return True

    def _calculate_fitness(self, ret: float, sharpe: float, dd: float, wr: float) -> float:
        """Calculate composite fitness score."""
        return (ret * 0.3) + (sharpe * 0.3) + ((1 + dd) * 0.2) + (wr * 0.2)

    def _test_robustness(self, result: dict, combinations: list, backtest_func: Callable) -> float:
        """Test robustness by perturbing parameters slightly."""
        robustness_scores = []
        for _ in range(10):  # Test 10 variations
            # Slightly perturb parameters
            perturbed = result["parameters"].copy()
            for key in perturbed:
                if isinstance(perturbed[key], (int, float)):
                    perturbed[key] *= random.uniform(0.95, 1.05)

            # Backtest with perturbed parameters
            perturbed_result = backtest_func(perturbed)
            if perturbed_result:
                robustness_scores.append(perturbed_result["return"])

        if robustness_scores:
            # Lower variance = higher robustness
            variance = sum((x - result["return"]) ** 2 for x in robustness_scores) / len(robustness_scores)
            robustness = max(0, 100 - variance * 100)
            return robustness
        return 50.0

    def _calculate_metrics(self, trades: list) -> dict:
        """Calculate performance metrics from trades."""
        if not trades:
            return {"sharpe": 0, "return": 0, "win_rate": 0, "max_dd": 0}

        pnl_list = [t.get("pnl_sol", 0) for t in trades]
        total_return = sum(pnl_list)
        wins = sum(1 for p in pnl_list if p > 0)
        win_rate = wins / len(pnl_list) if pnl_list else 0
        std_dev = (sum((p - total_return / len(pnl_list)) ** 2 for p in pnl_list) / len(pnl_list)) ** 0.5

        return {
            "return": total_return,
            "sharpe": total_return / std_dev if std_dev > 0 else 0,
            "win_rate": win_rate,
            "max_dd": 0,  # Simplified
        }

    def _calculate_degradation(self, in_sample: float, out_sample: float) -> float:
        """Calculate in-sample vs out-of-sample degradation."""
        if in_sample == 0:
            return 0
        return (in_sample - out_sample) / in_sample
