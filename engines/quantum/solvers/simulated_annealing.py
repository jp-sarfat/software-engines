"""
Simulated annealing fallback solver.
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


class SimulatedAnnealingSolver:
    def __init__(
        self,
        initial_temp: float = 100.0,
        final_temp: float = 0.001,
        cooling_rate: float = 0.99,
        iterations_per_temp: int = 100,
    ):
        self.initial_temp = initial_temp
        self.final_temp = final_temp
        self.cooling_rate = cooling_rate
        self.iterations_per_temp = iterations_per_temp
        self.encoder = QUBOEncoder()

    def solve(
        self,
        problem: Problem,
        timeout_seconds: float = 300,
        num_runs: int = 10,
        **kwargs,
    ) -> QuantumResult:
        start = time.time()
        try:
            encoded = self.encoder.encode(problem)
            Q = encoded["qubo_matrix"]
            n = encoded["num_variables"]

            best_solution = None
            best_energy = float("inf")
            all_solutions: list[tuple] = []

            for _ in range(num_runs):
                if time.time() - start > timeout_seconds:
                    break
                sol, energy = self._anneal(Q)
                all_solutions.append((sol.copy(), energy))
                if energy < best_energy:
                    best_energy = energy
                    best_solution = sol.copy()

            elapsed = (time.time() - start) * 1000
            return QuantumResult(
                solution=best_solution,
                solution_dict={
                    encoded["variable_names"][i]: int(best_solution[i])
                    for i in range(n)
                } if best_solution is not None else {},
                all_solutions=[s for s, _ in sorted(all_solutions, key=lambda x: x[1])[:10]],
                status=ResultStatus.SUCCESS,
                solver_type=SolverType.CLASSICAL_SIMULATED_ANNEALING,
                solver_name="Simulated Annealing",
                timing=TimingInfo(total_time_ms=elapsed, execution_time_ms=elapsed),
                quality=QualityMetrics(
                    energy=best_energy,
                    objective_value=best_energy + encoded.get("offset", 0),
                    confidence=0.9,
                    num_shots=num_runs,
                ),
                problem_name=problem.name,
            )
        except Exception as e:
            logger.error("Simulated annealing error: %s", e, exc_info=True)
            return QuantumResult.from_error(e, problem_name=problem.name)

    def _anneal(self, Q: np.ndarray) -> tuple[np.ndarray, float]:
        n = Q.shape[0]
        solution = np.random.randint(0, 2, n)
        energy = float(solution @ Q @ solution)
        best_solution = solution.copy()
        best_energy = energy
        temp = self.initial_temp

        while temp > self.final_temp:
            for _ in range(self.iterations_per_temp):
                flip = np.random.randint(n)
                new = solution.copy()
                new[flip] = 1 - new[flip]
                new_energy = float(new @ Q @ new)
                delta = new_energy - energy
                if delta < 0 or np.random.random() < np.exp(-delta / temp):
                    solution = new
                    energy = new_energy
                    if energy < best_energy:
                        best_energy = energy
                        best_solution = solution.copy()
            temp *= self.cooling_rate
        return best_solution, best_energy
