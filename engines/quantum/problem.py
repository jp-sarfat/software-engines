"""
Quantum problem definition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

import numpy as np
from numpy.typing import NDArray


class ProblemType(str, Enum):
    QUBO = "qubo"
    ISING = "ising"
    MAXCUT = "maxcut"
    TSP = "tsp"
    VRP = "vrp"
    SCHEDULING = "scheduling"
    RESOURCE_ALLOCATION = "resource_allocation"
    PORTFOLIO = "portfolio"
    CLASSIFICATION = "classification"
    CLUSTERING = "clustering"
    SEARCH = "search"
    CUSTOM = "custom"


class ObjectiveType(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


@dataclass
class Constraint:
    name: str
    expression: Any
    constraint_type: str = "le"
    rhs: float = 0.0
    penalty: float = 1.0


@dataclass
class Variable:
    name: str
    var_type: str = "binary"
    lower_bound: float = 0.0
    upper_bound: float = 1.0
    initial_value: Optional[float] = None


@dataclass
class Problem:
    name: str
    problem_type: ProblemType = ProblemType.QUBO
    objective: ObjectiveType = ObjectiveType.MINIMIZE

    variables: list[Variable] = field(default_factory=list)
    num_variables: Optional[int] = None
    constraints: list[Constraint] = field(default_factory=list)

    objective_function: Optional[Callable] = None
    qubo_matrix: Optional[NDArray] = None
    qubo_dict: Optional[dict[tuple[int, int], float]] = None
    ising_h: Optional[NDArray] = None
    ising_j: Optional[dict[tuple[int, int], float]] = None

    graph: Optional[Any] = None
    distance_matrix: Optional[NDArray] = None
    weights: Optional[NDArray] = None
    data: Optional[dict[str, Any]] = None

    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    preferred_provider: Optional[str] = None
    max_time_seconds: Optional[float] = None

    def __post_init__(self):
        if self.num_variables is None:
            if self.qubo_matrix is not None:
                self.num_variables = self.qubo_matrix.shape[0]
            elif self.qubo_dict:
                self.num_variables = max(max(k) for k in self.qubo_dict) + 1
            elif self.graph is not None:
                self.num_variables = self.graph.number_of_nodes()
            elif self.distance_matrix is not None:
                self.num_variables = self.distance_matrix.shape[0]
            elif self.variables:
                self.num_variables = len(self.variables)

        if not self.variables and self.num_variables:
            self.variables = [
                Variable(name=f"x_{i}") for i in range(self.num_variables)
            ]

    @classmethod
    def from_qubo_matrix(
        cls,
        Q: NDArray,
        name: str = "QUBO Problem",
        objective: ObjectiveType = ObjectiveType.MINIMIZE,
        **kwargs: Any,
    ) -> Problem:
        return cls(
            name=name,
            problem_type=ProblemType.QUBO,
            objective=objective,
            qubo_matrix=np.array(Q),
            **kwargs,
        )

    @classmethod
    def from_qubo_dict(
        cls,
        qubo: dict[tuple[int, int], float],
        name: str = "QUBO Problem",
        objective: ObjectiveType = ObjectiveType.MINIMIZE,
        **kwargs: Any,
    ) -> Problem:
        return cls(
            name=name,
            problem_type=ProblemType.QUBO,
            objective=objective,
            qubo_dict=qubo,
            **kwargs,
        )

    @classmethod
    def from_maxcut(cls, graph: Any, name: str = "MaxCut Problem", **kw: Any) -> Problem:
        return cls(
            name=name,
            problem_type=ProblemType.MAXCUT,
            objective=ObjectiveType.MAXIMIZE,
            graph=graph,
            **kw,
        )

    @classmethod
    def from_tsp(
        cls, distance_matrix: NDArray, name: str = "TSP Problem", **kw: Any
    ) -> Problem:
        return cls(
            name=name,
            problem_type=ProblemType.TSP,
            objective=ObjectiveType.MINIMIZE,
            distance_matrix=np.array(distance_matrix),
            **kw,
        )

    @classmethod
    def from_scheduling(
        cls,
        jobs: list[dict[str, Any]],
        resources: list[dict[str, Any]],
        constraints: list[Constraint] | None = None,
        name: str = "Scheduling Problem",
        **kw: Any,
    ) -> Problem:
        return cls(
            name=name,
            problem_type=ProblemType.SCHEDULING,
            objective=ObjectiveType.MINIMIZE,
            constraints=constraints or [],
            data={"jobs": jobs, "resources": resources},
            **kw,
        )

    def to_qubo_matrix(self) -> NDArray:
        if self.qubo_matrix is not None:
            return self.qubo_matrix
        if self.qubo_dict is not None:
            n = self.num_variables or max(max(k) for k in self.qubo_dict) + 1
            Q = np.zeros((n, n))
            for (i, j), val in self.qubo_dict.items():
                Q[i, j] = val
                if i != j:
                    Q[j, i] = val
            return Q
        if self.ising_h is not None and self.ising_j is not None:
            return self._ising_to_qubo()
        raise ValueError(f"Cannot convert {self.problem_type} to QUBO matrix")

    def _ising_to_qubo(self) -> NDArray:
        h = self.ising_h
        J = self.ising_j
        n = len(h)  # type: ignore[arg-type]
        Q = np.zeros((n, n))
        for i in range(n):
            Q[i, i] = -2 * h[i]  # type: ignore[index]
        for (i, j), val in J.items():  # type: ignore[union-attr]
            Q[i, j] = 4 * val
            Q[j, i] = 4 * val
        return Q

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.name:
            errors.append("Problem must have a name")
        if self.num_variables is None or self.num_variables <= 0:
            errors.append("Problem must have at least one variable")
        if self.qubo_matrix is not None and not np.allclose(
            self.qubo_matrix, self.qubo_matrix.T
        ):
            errors.append("QUBO matrix must be symmetric")
        return errors

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.problem_type.value,
            "objective": self.objective.value,
            "num_variables": self.num_variables,
            "num_constraints": len(self.constraints),
            "tags": self.tags,
        }
