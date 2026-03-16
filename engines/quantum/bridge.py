"""
QuantumBridge – main entry point for quantum/classical optimization.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from engines.quantum.config import (
    QuantumConfig,
    ExecutionMode,
    ProviderType,
    FallbackStrategy,
)
from engines.quantum.problem import Problem, ProblemType
from engines.quantum.result import QuantumResult
from engines.quantum.orchestrator import TaskOrchestrator
from engines.quantum.budget import BudgetManager
from engines.quantum.classifier import ProblemClassifier

logger = logging.getLogger(__name__)


class QuantumBridge:
    def __init__(
        self,
        config: Optional[QuantumConfig] = None,
        provider: Optional[ProviderType] = None,
        mode: Optional[ExecutionMode] = None,
    ):
        self.config = config or QuantumConfig.from_env()
        if provider:
            self.config.default_provider = provider
        if mode:
            self.config.mode = mode
        self.orchestrator = TaskOrchestrator(self.config)
        self.budget = BudgetManager(self.config.budget)
        self.classifier = ProblemClassifier()

    def solve(
        self,
        problem: Problem,
        provider: Optional[ProviderType] = None,
        force_classical: bool = False,
        force_quantum: bool = False,
        timeout_seconds: float = 300,
    ) -> QuantumResult:
        start = time.time()
        try:
            errors = problem.validate()
            if errors:
                return QuantumResult.from_error(
                    ValueError(f"Invalid problem: {errors}"),
                    problem_name=problem.name,
                )
            if not self.budget.can_execute():
                force_classical = True

            strategy = self._determine_strategy(problem, provider, force_classical, force_quantum)
            result = self.orchestrator.execute(problem, strategy, timeout_seconds)

            if result.is_success:
                self.budget.record_usage(
                    cost_usd=result.cost.estimated_cost_usd,
                    time_seconds=result.timing.total_time_ms / 1000,
                )
            result.timing.total_time_ms = (time.time() - start) * 1000
            return result
        except Exception as e:
            return QuantumResult.from_error(e, problem_name=problem.name)

    async def solve_async(self, problem: Problem, **kwargs) -> QuantumResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.solve(problem, **kwargs))

    def solve_batch(
        self,
        problems: list[Problem],
        parallel: bool = True,
        max_concurrent: int | None = None,
    ) -> list[QuantumResult]:
        if not parallel:
            return [self.solve(p) for p in problems]
        mc = max_concurrent or self.config.max_concurrent_tasks

        async def _run():
            sem = asyncio.Semaphore(mc)

            async def _one(p):
                async with sem:
                    return await self.solve_async(p)

            return await asyncio.gather(*[_one(p) for p in problems])

        return asyncio.run(_run())

    def _determine_strategy(
        self,
        problem: Problem,
        provider: Optional[ProviderType],
        force_classical: bool,
        force_quantum: bool,
    ) -> dict[str, Any]:
        strategy: dict[str, Any] = {
            "provider": provider or self.config.default_provider,
            "use_quantum": False,
            "fallback": self.config.fallback_strategy,
            "mode": self.config.mode,
        }
        if force_classical:
            strategy["fallback"] = FallbackStrategy.SIMULATED_ANNEALING
            return strategy
        if force_quantum:
            strategy["use_quantum"] = True
            strategy["fallback"] = FallbackStrategy.NONE
            return strategy
        if self.config.mode == ExecutionMode.LOCAL:
            strategy["provider"] = ProviderType.LOCAL
        elif self.config.mode in (ExecutionMode.PRODUCTION, ExecutionMode.HYBRID):
            classification = self.classifier.classify(problem)
            strategy["use_quantum"] = classification["quantum_suitable"]
        return strategy

    # Convenience helpers
    def optimize_qubo(self, Q, name="QUBO Optimization", **kw) -> QuantumResult:
        return self.solve(Problem.from_qubo_matrix(Q, name=name), **kw)

    def optimize_maxcut(self, graph, name="MaxCut Optimization", **kw) -> QuantumResult:
        return self.solve(Problem.from_maxcut(graph, name=name), **kw)

    def optimize_tsp(self, distance_matrix, name="TSP Optimization", **kw) -> QuantumResult:
        return self.solve(Problem.from_tsp(distance_matrix, name=name), **kw)

    def get_status(self) -> dict[str, Any]:
        return {
            "mode": self.config.mode.value,
            "default_provider": self.config.default_provider.value,
            "budget": {
                "remaining_usd": self.budget.remaining_usd,
                "remaining_time_seconds": self.budget.remaining_time_seconds,
                "usage_percentage": self.budget.usage_percentage,
            },
        }

    def reset_budget(self) -> None:
        self.budget.reset()
