"""
Tests for quantum problem definitions.
"""

import numpy as np
import networkx as nx

from engines.quantum.problem import Problem, ProblemType, ObjectiveType, Variable


class TestProblemCreation:
    def test_from_qubo_matrix(self):
        Q = np.array([[-1, 2], [2, -1]])
        p = Problem.from_qubo_matrix(Q, name="Test QUBO")
        assert p.name == "Test QUBO"
        assert p.problem_type == ProblemType.QUBO
        assert p.num_variables == 2
        assert len(p.variables) == 2

    def test_from_qubo_dict(self):
        qubo = {(0, 0): -1, (1, 1): -1, (0, 1): 2}
        p = Problem.from_qubo_dict(qubo)
        assert p.problem_type == ProblemType.QUBO
        assert p.num_variables == 2

    def test_from_maxcut(self):
        G = nx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 0)])
        p = Problem.from_maxcut(G)
        assert p.problem_type == ProblemType.MAXCUT
        assert p.objective == ObjectiveType.MAXIMIZE

    def test_from_tsp(self):
        D = np.array([[0, 10, 15], [10, 0, 20], [15, 20, 0]])
        p = Problem.from_tsp(D)
        assert p.problem_type == ProblemType.TSP
        assert p.distance_matrix is not None

    def test_from_scheduling(self):
        jobs = [{"name": "j1", "deadline": 5}]
        resources = [{"name": "r1"}]
        p = Problem.from_scheduling(jobs, resources)
        assert p.problem_type == ProblemType.SCHEDULING
        assert p.data is not None


class TestProblemConversion:
    def test_to_qubo_matrix_from_matrix(self):
        Q = np.array([[-1, 0.5], [0.5, -1]])
        p = Problem.from_qubo_matrix(Q)
        result = p.to_qubo_matrix()
        np.testing.assert_array_equal(result, Q)

    def test_to_qubo_matrix_from_dict(self):
        qubo = {(0, 0): -1, (1, 1): -1, (0, 1): 2}
        p = Problem.from_qubo_dict(qubo)
        Q = p.to_qubo_matrix()
        assert Q.shape == (2, 2)
        assert Q[0, 0] == -1
        assert Q[0, 1] == 2


class TestProblemValidation:
    def test_valid_problem(self):
        Q = np.array([[-1, 2], [2, -1]])
        p = Problem.from_qubo_matrix(Q)
        assert p.validate() == []

    def test_no_name(self):
        p = Problem(name="", qubo_matrix=np.array([[1]]))
        errors = p.validate()
        assert any("name" in e for e in errors)

    def test_no_variables(self):
        p = Problem(name="bad")
        errors = p.validate()
        assert len(errors) > 0

    def test_asymmetric_matrix(self):
        Q = np.array([[1, 2], [3, 4]])
        p = Problem.from_qubo_matrix(Q)
        errors = p.validate()
        assert any("symmetric" in e for e in errors)


class TestProblemSummary:
    def test_summary(self):
        Q = np.array([[-1, 2], [2, -1]])
        p = Problem.from_qubo_matrix(Q, name="Test")
        s = p.summary()
        assert s["name"] == "Test"
        assert s["type"] == "qubo"
        assert s["num_variables"] == 2
