"""
Tests for QUBO encoder.
"""

import numpy as np
import networkx as nx

from engines.quantum.encoders.qubo import QUBOEncoder
from engines.quantum.problem import Problem, ProblemType


class TestQUBOEncoder:
    def setup_method(self):
        self.encoder = QUBOEncoder()

    def test_encode_qubo(self):
        Q = np.array([[-1, 2], [2, -1]])
        p = Problem.from_qubo_matrix(Q)
        encoded = self.encoder.encode(p)
        assert encoded["num_variables"] == 2
        np.testing.assert_array_equal(encoded["qubo_matrix"], Q)

    def test_encode_maxcut(self):
        G = nx.Graph()
        G.add_edges_from([(0, 1), (1, 2)])
        p = Problem.from_maxcut(G)
        encoded = self.encoder.encode(p)
        assert encoded["num_variables"] == 3
        assert encoded["qubo_matrix"].shape == (3, 3)

    def test_encode_tsp(self):
        D = np.array([[0, 10], [10, 0]])
        p = Problem.from_tsp(D)
        encoded = self.encoder.encode(p)
        assert encoded["num_variables"] == 4
        assert encoded["num_cities"] == 2

    def test_encode_scheduling(self):
        jobs = [{"name": "j1", "deadline": 3}]
        resources = [{"name": "r1"}]
        p = Problem.from_scheduling(jobs, resources)
        encoded = self.encoder.encode(p)
        assert encoded["num_jobs"] == 1
        assert encoded["num_resources"] == 1

    def test_decode_qubo(self):
        Q = np.array([[-1, 2], [2, -1]])
        p = Problem.from_qubo_matrix(Q)
        decoded = self.encoder.decode(np.array([1, 0]), p)
        assert decoded["num_selected"] == 1
        assert decoded["selected_indices"] == [0]

    def test_validate_unsupported_type(self):
        p = Problem(name="custom", problem_type=ProblemType.CUSTOM, num_variables=5)
        errors = self.encoder.validate(p)
        assert len(errors) > 0

    def test_validate_maxcut_no_graph(self):
        p = Problem(name="bad maxcut", problem_type=ProblemType.MAXCUT, num_variables=3)
        errors = self.encoder.validate(p)
        assert any("graph" in e.lower() for e in errors)
