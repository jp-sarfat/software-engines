"""
Tests for classical solvers (simulated annealing and brute force).
"""

import numpy as np

from engines.quantum.solvers.simulated_annealing import SimulatedAnnealingSolver
from engines.quantum.solvers.classical import ClassicalOptimizer
from engines.quantum.problem import Problem
from engines.quantum.result import ResultStatus, SolverType


class TestSimulatedAnnealing:
    def test_solves_simple_qubo(self):
        Q = np.array([[-1, 2], [2, -1]])
        p = Problem.from_qubo_matrix(Q, name="sa_test")
        solver = SimulatedAnnealingSolver(
            initial_temp=50, final_temp=0.01, cooling_rate=0.95, iterations_per_temp=50
        )
        result = solver.solve(p, num_runs=3)
        assert result.is_success
        assert result.solver_type == SolverType.CLASSICAL_SIMULATED_ANNEALING
        assert result.solution is not None
        assert len(result.solution) == 2

    def test_finds_optimal_trivial(self):
        Q = np.array([[1, 0], [0, 1]])
        p = Problem.from_qubo_matrix(Q, name="trivial")
        solver = SimulatedAnnealingSolver(
            initial_temp=100, final_temp=0.001, cooling_rate=0.95, iterations_per_temp=100
        )
        result = solver.solve(p, num_runs=5)
        assert result.is_success
        np.testing.assert_array_equal(result.solution, [0, 0])

    def test_result_has_timing(self):
        Q = np.array([[-1, 0], [0, -1]])
        p = Problem.from_qubo_matrix(Q)
        solver = SimulatedAnnealingSolver(
            initial_temp=10, final_temp=0.1, cooling_rate=0.9, iterations_per_temp=10
        )
        result = solver.solve(p, num_runs=1)
        assert result.timing.total_time_ms > 0


class TestClassicalOptimizer:
    def test_brute_force_small(self):
        Q = np.array([[-1, 2], [2, -1]])
        p = Problem.from_qubo_matrix(Q, name="brute_test")
        solver = ClassicalOptimizer()
        result = solver.solve(p)
        assert result.is_success
        assert result.solver_type == SolverType.CLASSICAL_OPTIMIZER
        assert result.quality.confidence == 1.0

    def test_finds_global_minimum(self):
        Q = np.array([[1, 0], [0, 1]])
        p = Problem.from_qubo_matrix(Q, name="min_test")
        solver = ClassicalOptimizer()
        result = solver.solve(p)
        np.testing.assert_array_equal(result.solution, [0, 0])
        assert result.quality.energy == 0.0

    def test_prefers_selected(self):
        Q = np.array([[-5, 0], [0, -3]])
        p = Problem.from_qubo_matrix(Q, name="select_test")
        solver = ClassicalOptimizer()
        result = solver.solve(p)
        np.testing.assert_array_equal(result.solution, [1, 1])
        assert result.quality.energy == -8.0
