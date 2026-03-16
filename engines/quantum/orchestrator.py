"""
Task orchestrator – manages quantum/classical execution with fallback.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from engines.quantum.config import QuantumConfig, ProviderType, FallbackStrategy
from engines.quantum.problem import Problem
from engines.quantum.result import QuantumResult, ResultStatus

logger = logging.getLogger(__name__)


class TaskOrchestrator:
    def __init__(self, config: QuantumConfig):
        self.config = config
        self._providers: dict[ProviderType, Any] = {}
        self._fallbacks: dict[FallbackStrategy, Any] = {}
        self._init_fallbacks()

    def _init_fallbacks(self) -> None:
        from engines.quantum.solvers.simulated_annealing import SimulatedAnnealingSolver
        from engines.quantum.solvers.classical import ClassicalOptimizer

        self._fallbacks[FallbackStrategy.SIMULATED_ANNEALING] = SimulatedAnnealingSolver()
        self._fallbacks[FallbackStrategy.CLASSICAL_OPTIMIZER] = ClassicalOptimizer()

    def execute(
        self,
        problem: Problem,
        strategy: dict[str, Any],
        timeout_seconds: float = 300,
    ) -> QuantumResult:
        start = time.time()
        use_quantum = strategy.get("use_quantum", False)
        provider_type = strategy.get("provider", self.config.default_provider)
        fallback = strategy.get("fallback", self.config.fallback_strategy)

        if use_quantum and provider_type != ProviderType.LOCAL:
            try:
                provider = self._get_or_create_provider(provider_type)
                if provider is not None:
                    result = provider.solve(problem, timeout_seconds=timeout_seconds)
                    if result.is_success:
                        return result
            except Exception as exc:
                logger.warning("Quantum execution error: %s", exc)

        if fallback != FallbackStrategy.NONE:
            return self._execute_classical(
                problem, fallback, is_fallback=use_quantum,
                timeout_seconds=timeout_seconds - (time.time() - start),
            )

        return QuantumResult.from_error(
            RuntimeError("No solver available"), problem_name=problem.name
        )

    def _execute_classical(
        self,
        problem: Problem,
        strategy: FallbackStrategy,
        is_fallback: bool,
        timeout_seconds: float,
    ) -> QuantumResult:
        solver = self._fallbacks.get(strategy)
        if solver is None:
            return QuantumResult.from_error(
                RuntimeError(f"Fallback solver {strategy.value} not available"),
                problem_name=problem.name,
            )
        start = time.time()
        result = solver.solve(problem, timeout_seconds=timeout_seconds)
        if is_fallback:
            result.status = ResultStatus.FALLBACK
        result.timing.total_time_ms = (time.time() - start) * 1000
        return result

    def _get_or_create_provider(self, pt: ProviderType) -> Optional[Any]:
        if pt in self._providers:
            return self._providers[pt]
        provider = self._create_provider(pt)
        if provider is not None:
            self._providers[pt] = provider
        return provider

    def _create_provider(self, pt: ProviderType) -> Optional[Any]:
        if pt == ProviderType.LOCAL:
            from engines.quantum.providers.local import LocalSimulatorProvider
            return LocalSimulatorProvider()
        logger.warning("Provider %s not available in this build", pt.value)
        return None

    def get_provider_status(self, pt: ProviderType) -> dict[str, Any]:
        p = self._providers.get(pt)
        if p is None:
            return {"available": False, "reason": "Not initialised"}
        try:
            return p.get_status()
        except Exception as e:
            return {"available": False, "reason": str(e)}
