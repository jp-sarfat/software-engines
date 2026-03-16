"""
Tests for problem classifier.
"""

import numpy as np

from engines.quantum.classifier import ProblemClassifier
from engines.quantum.problem import Problem, ProblemType
from engines.quantum.config import ProviderType


class TestProblemClassifier:
    def setup_method(self):
        self.classifier = ProblemClassifier()

    def test_trivial_qubo(self):
        Q = np.zeros((3, 3))
        p = Problem.from_qubo_matrix(Q, name="tiny")
        result = self.classifier.classify(p)
        assert not result["quantum_suitable"]
        assert result["complexity"] == "trivial"

    def test_medium_qubo(self):
        Q = np.zeros((100, 100))
        p = Problem.from_qubo_matrix(Q, name="medium")
        result = self.classifier.classify(p)
        assert result["quantum_suitable"]
        assert result["complexity"] == "medium"

    def test_unsupported_type(self):
        p = Problem(name="custom", problem_type=ProblemType.CUSTOM, num_variables=50)
        result = self.classifier.classify(p)
        assert not result["quantum_suitable"]

    def test_recommends_dwave_for_qubo(self):
        Q = np.zeros((100, 100))
        p = Problem.from_qubo_matrix(Q, name="big qubo")
        result = self.classifier.classify(p)
        assert result["recommended_provider"] == ProviderType.DWAVE

    def test_estimate_resources(self):
        Q = np.zeros((50, 50))
        p = Problem.from_qubo_matrix(Q, name="est")
        est = self.classifier.estimate_resources(p)
        assert est["logical_qubits"] == 50
        assert est["physical_qubits_estimated"] == 150
