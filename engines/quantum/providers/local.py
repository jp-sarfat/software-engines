"""
Local simulator provider – uses simulated annealing.
"""

from __future__ import annotations

from typing import Any

from engines.quantum.providers.base import BaseProvider
from engines.quantum.problem import Problem
from engines.quantum.result import QuantumResult
from engines.quantum.solvers.simulated_annealing import SimulatedAnnealingSolver


class LocalSimulatorProvider(BaseProvider):
    def __init__(self, max_qubits: int = 30):
        self._solver = SimulatedAnnealingSolver()
        self.max_qubits = max_qubits

    @property
    def name(self) -> str:
        return "Local Simulator"

    @property
    def is_available(self) -> bool:
        return True

    def solve(self, problem: Problem, timeout_seconds: float = 300, **kw) -> QuantumResult:
        return self._solver.solve(problem, timeout_seconds=timeout_seconds)

    def get_status(self) -> dict[str, Any]:
        return {
            "available": True,
            "name": self.name,
            "max_qubits": self.max_qubits,
        }
