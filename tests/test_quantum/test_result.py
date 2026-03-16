"""
Tests for quantum result types.
"""

import numpy as np

from engines.quantum.result import (
    QuantumResult,
    ResultStatus,
    SolverType,
    TimingInfo,
    QualityMetrics,
    CostInfo,
)


class TestQuantumResult:
    def test_success_status(self):
        r = QuantumResult(status=ResultStatus.SUCCESS)
        assert r.is_success

    def test_fallback_is_success(self):
        r = QuantumResult(status=ResultStatus.FALLBACK)
        assert r.is_success

    def test_error_is_not_success(self):
        r = QuantumResult(status=ResultStatus.ERROR)
        assert not r.is_success

    def test_is_quantum(self):
        r = QuantumResult(solver_type=SolverType.QUANTUM_ANNEALER)
        assert r.is_quantum

    def test_is_not_quantum(self):
        r = QuantumResult(solver_type=SolverType.CLASSICAL_SIMULATED_ANNEALING)
        assert not r.is_quantum

    def test_selected_indices(self):
        r = QuantumResult(solution=np.array([1, 0, 1, 0, 1]))
        assert r.get_selected_indices() == [0, 2, 4]

    def test_selected_indices_none(self):
        r = QuantumResult(solution=None)
        assert r.get_selected_indices() == []

    def test_from_error(self):
        r = QuantumResult.from_error(ValueError("test"), problem_name="p1")
        assert r.status == ResultStatus.ERROR
        assert "test" in r.error_message
        assert r.problem_name == "p1"

    def test_from_timeout(self):
        r = QuantumResult.from_timeout(problem_name="p2")
        assert r.status == ResultStatus.TIMEOUT

    def test_summary(self):
        r = QuantumResult(
            solution=np.array([1, 0]),
            status=ResultStatus.SUCCESS,
            solver_type=SolverType.LOCAL_SIMULATOR,
            quality=QualityMetrics(energy=-5.0),
            timing=TimingInfo(total_time_ms=42.0),
        )
        s = r.summary()
        assert s["status"] == "success"
        assert s["energy"] == -5.0
        assert s["total_time_ms"] == 42.0


class TestQualityMetrics:
    def test_constraint_satisfaction_rate(self):
        m = QualityMetrics(constraints_satisfied=3, constraints_total=4)
        assert m.constraint_satisfaction_rate == 0.75

    def test_no_constraints(self):
        m = QualityMetrics()
        assert m.constraint_satisfaction_rate == 1.0
