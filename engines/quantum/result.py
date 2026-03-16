"""
Quantum computation result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import numpy as np
from numpy.typing import NDArray


class SolverType(str, Enum):
    QUANTUM_GATE = "quantum_gate"
    QUANTUM_ANNEALER = "quantum_annealer"
    CLASSICAL_SIMULATED_ANNEALING = "classical_sa"
    CLASSICAL_GENETIC = "classical_genetic"
    CLASSICAL_OPTIMIZER = "classical_optimizer"
    HYBRID = "hybrid"
    LOCAL_SIMULATOR = "local_simulator"


class ResultStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    ERROR = "error"
    FALLBACK = "fallback"


@dataclass
class TimingInfo:
    total_time_ms: float = 0.0
    queue_time_ms: float = 0.0
    execution_time_ms: float = 0.0
    post_processing_time_ms: float = 0.0


@dataclass
class QualityMetrics:
    energy: Optional[float] = None
    objective_value: Optional[float] = None
    confidence: float = 1.0
    num_shots: int = 1
    solution_frequency: float = 1.0
    constraints_satisfied: int = 0
    constraints_total: int = 0

    @property
    def constraint_satisfaction_rate(self) -> float:
        if self.constraints_total == 0:
            return 1.0
        return self.constraints_satisfied / self.constraints_total


@dataclass
class CostInfo:
    estimated_cost_usd: float = 0.0
    actual_cost_usd: Optional[float] = None
    shots_charged: int = 0
    task_cost_usd: float = 0.0


@dataclass
class QuantumResult:
    solution: Optional[NDArray] = None
    solution_dict: dict[str, int] = field(default_factory=dict)
    all_solutions: list[NDArray] = field(default_factory=list)
    status: ResultStatus = ResultStatus.SUCCESS
    error_message: Optional[str] = None
    solver_type: SolverType = SolverType.LOCAL_SIMULATOR
    solver_name: str = "Unknown"
    timing: TimingInfo = field(default_factory=TimingInfo)
    quality: QualityMetrics = field(default_factory=QualityMetrics)
    cost: CostInfo = field(default_factory=CostInfo)
    problem_name: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status in (ResultStatus.SUCCESS, ResultStatus.PARTIAL, ResultStatus.FALLBACK)

    @property
    def is_quantum(self) -> bool:
        return self.solver_type in (
            SolverType.QUANTUM_GATE,
            SolverType.QUANTUM_ANNEALER,
            SolverType.HYBRID,
        )

    def get_selected_indices(self) -> list[int]:
        if self.solution is None:
            return []
        return [i for i, v in enumerate(self.solution) if v == 1]

    def summary(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "solver": self.solver_type.value,
            "solver_name": self.solver_name,
            "is_quantum": self.is_quantum,
            "solution_size": len(self.solution) if self.solution is not None else 0,
            "selected_count": len(self.get_selected_indices()),
            "energy": self.quality.energy,
            "objective_value": self.quality.objective_value,
            "confidence": self.quality.confidence,
            "total_time_ms": self.timing.total_time_ms,
            "cost_usd": self.cost.actual_cost_usd or self.cost.estimated_cost_usd,
        }

    @classmethod
    def from_error(
        cls,
        error: Exception,
        problem_name: str = "",
        solver_type: SolverType = SolverType.LOCAL_SIMULATOR,
    ) -> QuantumResult:
        return cls(
            status=ResultStatus.ERROR,
            error_message=str(error),
            solver_type=solver_type,
            problem_name=problem_name,
        )

    @classmethod
    def from_timeout(
        cls, problem_name: str = "", partial_solution: Optional[NDArray] = None
    ) -> QuantumResult:
        return cls(
            status=ResultStatus.TIMEOUT,
            solution=partial_solution,
            problem_name=problem_name,
            error_message="Computation timed out",
        )
