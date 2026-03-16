"""
Tests for QuantumBridge.
"""

import numpy as np
import networkx as nx

from engines.quantum.bridge import QuantumBridge
from engines.quantum.config import QuantumConfig, ExecutionMode, ProviderType
from engines.quantum.problem import Problem
from engines.quantum.result import ResultStatus


class TestQuantumBridge:
    def setup_method(self):
        self.bridge = QuantumBridge(config=QuantumConfig.for_local_development())

    def test_solve_qubo(self):
        Q = np.array([[-1, 2], [2, -1]])
        p = Problem.from_qubo_matrix(Q, name="bridge_test")
        result = self.bridge.solve(p)
        assert result.is_success
        assert result.solution is not None

    def test_optimize_qubo(self):
        Q = np.array([[1, 0], [0, 1]])
        result = self.bridge.optimize_qubo(Q)
        assert result.is_success

    def test_optimize_maxcut(self):
        G = nx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 0)])
        result = self.bridge.optimize_maxcut(G)
        assert result.is_success

    def test_optimize_tsp(self):
        D = np.array([[0, 10], [10, 0]])
        result = self.bridge.optimize_tsp(D)
        assert result.is_success

    def test_force_classical(self):
        Q = np.array([[-1, 0], [0, -1]])
        p = Problem.from_qubo_matrix(Q)
        result = self.bridge.solve(p, force_classical=True)
        assert result.is_success
        assert not result.is_quantum

    def test_invalid_problem(self):
        p = Problem(name="")
        result = self.bridge.solve(p)
        assert result.status == ResultStatus.ERROR

    def test_get_status(self):
        status = self.bridge.get_status()
        assert status["mode"] == "local"
        assert "budget" in status

    def test_reset_budget(self):
        self.bridge.budget.record_usage(10, 60)
        assert self.bridge.budget.remaining_usd < 100
        self.bridge.reset_budget()
        assert self.bridge.budget.remaining_usd == 100.0

    def test_solve_batch(self):
        problems = [
            Problem.from_qubo_matrix(np.array([[1, 0], [0, 1]]), name=f"batch_{i}")
            for i in range(3)
        ]
        results = self.bridge.solve_batch(problems, parallel=False)
        assert len(results) == 3
        assert all(r.is_success for r in results)
