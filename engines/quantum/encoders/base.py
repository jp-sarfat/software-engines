"""
Abstract base encoder for problem encoding.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from engines.quantum.problem import Problem


class BaseEncoder(ABC):
    @abstractmethod
    def encode(self, problem: Problem) -> dict[str, Any]:
        ...

    @abstractmethod
    def decode(self, solution: Any, problem: Problem) -> dict[str, Any]:
        ...

    def validate(self, problem: Problem) -> list[str]:
        return []
