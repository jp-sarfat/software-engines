"""
Problem classifier – determines quantum suitability and recommends providers.
"""

from __future__ import annotations

import logging
from typing import Any

from engines.quantum.problem import Problem, ProblemType
from engines.quantum.config import ProviderType

logger = logging.getLogger(__name__)

QUANTUM_SUITABLE_TYPES = {
    ProblemType.QUBO,
    ProblemType.ISING,
    ProblemType.MAXCUT,
    ProblemType.TSP,
    ProblemType.VRP,
    ProblemType.SCHEDULING,
    ProblemType.RESOURCE_ALLOCATION,
    ProblemType.PORTFOLIO,
}

COMPLEXITY_THRESHOLDS = {
    "trivial": 10,
    "small": 50,
    "medium": 200,
    "large": 1000,
    "very_large": 5000,
}


class ProblemClassifier:
    def classify(self, problem: Problem) -> dict[str, Any]:
        result: dict[str, Any] = {
            "quantum_suitable": False,
            "recommended_provider": ProviderType.LOCAL,
            "algorithm": "classical",
            "complexity": "trivial",
            "confidence": 0.0,
            "reasons": [],
        }

        if problem.problem_type not in QUANTUM_SUITABLE_TYPES:
            result["reasons"].append(
                f"Problem type {problem.problem_type.value} not typically quantum-suitable"
            )
            return result

        num_vars = problem.num_variables or 0
        complexity = self._classify_complexity(num_vars)
        result["complexity"] = complexity

        if complexity == "trivial":
            result["reasons"].append(
                f"Problem size ({num_vars} variables) too small for quantum advantage"
            )
            return result

        result["quantum_suitable"] = True
        result["recommended_provider"] = self._recommend_provider(problem, num_vars)
        result["algorithm"] = self._recommend_algorithm(problem)
        result["confidence"] = self._calculate_confidence(problem, complexity)
        result["reasons"].append(
            f"Problem type {problem.problem_type.value} with {num_vars} variables "
            "is suitable for quantum computing"
        )
        return result

    @staticmethod
    def _classify_complexity(n: int) -> str:
        if n < COMPLEXITY_THRESHOLDS["trivial"]:
            return "trivial"
        if n < COMPLEXITY_THRESHOLDS["small"]:
            return "small"
        if n < COMPLEXITY_THRESHOLDS["medium"]:
            return "medium"
        if n < COMPLEXITY_THRESHOLDS["large"]:
            return "large"
        return "very_large"

    @staticmethod
    def _recommend_provider(problem: Problem, num_vars: int) -> ProviderType:
        if problem.problem_type in (ProblemType.QUBO, ProblemType.ISING) and num_vars <= 5000:
            return ProviderType.DWAVE
        if num_vars <= 30:
            return ProviderType.IONQ
        return ProviderType.AWS_BRAKET

    @staticmethod
    def _recommend_algorithm(problem: Problem) -> str:
        if problem.problem_type in (ProblemType.QUBO, ProblemType.ISING):
            return "quantum_annealing"
        if problem.problem_type in (ProblemType.MAXCUT, ProblemType.TSP, ProblemType.VRP):
            return "qaoa"
        if problem.problem_type == ProblemType.PORTFOLIO:
            return "vqe"
        return "hybrid"

    @staticmethod
    def _calculate_confidence(problem: Problem, complexity: str) -> float:
        base = {"trivial": 0.0, "small": 0.3, "medium": 0.6, "large": 0.8, "very_large": 0.9}
        conf = base.get(complexity, 0.5)
        if problem.problem_type in (ProblemType.QUBO, ProblemType.ISING):
            conf *= 1.2
        return min(1.0, conf)

    @staticmethod
    def estimate_resources(problem: Problem) -> dict[str, Any]:
        n = problem.num_variables or 0
        return {
            "logical_qubits": n,
            "physical_qubits_estimated": n * 3,
            "shots_recommended": 1000 if n <= 50 else 5000,
            "estimated_time_seconds": n * 0.1,
            "estimated_cost_usd": n * 0.001,
        }
