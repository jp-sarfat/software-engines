"""
Abstract base provider for quantum computing backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from engines.quantum.problem import Problem
from engines.quantum.result import QuantumResult


class BaseProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def solve(self, problem: Problem, timeout_seconds: float = 300, **kw) -> QuantumResult: ...

    @abstractmethod
    def get_status(self) -> dict[str, Any]: ...

    def supports_problem_type(self, problem: Problem) -> bool:
        return True


QuantumProvider = BaseProvider
