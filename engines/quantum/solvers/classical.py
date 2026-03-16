"""
Classical optimizer fallback using brute force / scipy.
"""

from __future__ import annotations

import logging
import time

import numpy as np

from engines.quantum.problem import Problem
from engines.quantum.result import (
    QuantumResult,
    ResultStatus,
    SolverType,
    TimingInfo,
    QualityMetrics,
)
from engines.quantum.encoders.qubo import QUBOEncoder

logger = logging.getLogger(__name__)


class ClassicalOptimizer:
    def __init__(self, method: str = "minimize"):
        self.method = method
        self.encoder = QUBOEncoder()

    def solve(self, problem: Problem, timeout_seconds: float = 300, **kwargs) -> QuantumResult:
        start = time.time()
        try:
            encoded = self.encoder.encode(problem)
            Q = encoded["qubo_matrix"]
            n = encoded["num_variables"]

            if n <= 20:
                solution, energy = self._brute_force(Q)
            else:
                solution, energy = self._scipy_optimize(Q)

            elapsed = (time.time() - start) * 1000
            return QuantumResult(
                solution=solution,
                solution_dict={
                    encoded["variable_names"][i]: int(solution[i]) for i in range(n)
                },
                status=ResultStatus.SUCCESS,
                solver_type=SolverType.CLASSICAL_OPTIMIZER,
                solver_name="Classical Optimizer",
                timing=TimingInfo(total_time_ms=elapsed, execution_time_ms=elapsed),
                quality=QualityMetrics(
                    energy=energy,
                    objective_value=energy + encoded.get("offset", 0),
                    confidence=1.0 if n <= 20 else 0.8,
                ),
                problem_name=problem.name,
            )
        except Exception as e:
            logger.error("Classical optimizer error: %s", e, exc_info=True)
            return QuantumResult.from_error(e, problem_name=problem.name)

    @staticmethod
    def _brute_force(Q: np.ndarray) -> tuple[np.ndarray, float]:
        n = Q.shape[0]
        best_sol = None
        best_e = float("inf")
        for i in range(2 ** n):
            sol = np.array([int(b) for b in format(i, f"0{n}b")])
            e = float(sol @ Q @ sol)
            if e < best_e:
                best_e = e
                best_sol = sol.copy()
        return best_sol, best_e  # type: ignore[return-value]

    @staticmethod
    def _scipy_optimize(Q: np.ndarray) -> tuple[np.ndarray, float]:
        from scipy.optimize import minimize

        n = Q.shape[0]

        def objective(x):
            return float(x @ Q @ x)

        best_sol = None
        best_e = float("inf")
        for _ in range(10):
            x0 = np.random.uniform(0, 1, n)
            res = minimize(objective, x0, bounds=[(0, 1)] * n, method="L-BFGS-B")
            sol = (res.x > 0.5).astype(int)
            e = float(sol @ Q @ sol)
            if e < best_e:
                best_e = e
                best_sol = sol
        return best_sol, best_e  # type: ignore[return-value]
