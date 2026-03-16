"""
Quantum Bridge configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class ExecutionMode(str, Enum):
    LOCAL = "local"
    PRODUCTION = "production"
    HYBRID = "hybrid"
    AUTO = "auto"


class ProviderType(str, Enum):
    AWS_BRAKET = "aws_braket"
    IBM_QUANTUM = "ibm_quantum"
    DWAVE = "dwave"
    IONQ = "ionq"
    RIGETTI = "rigetti"
    LOCAL = "local"
    AUTO = "auto"


class FallbackStrategy(str, Enum):
    SIMULATED_ANNEALING = "simulated_annealing"
    GENETIC_ALGORITHM = "genetic_algorithm"
    CLASSICAL_OPTIMIZER = "classical_optimizer"
    NONE = "none"


@dataclass
class ProviderConfig:
    provider_type: ProviderType
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    device_arn: Optional[str] = None
    region: str = "us-east-1"
    max_qubits: int = 30
    max_shots: int = 1000
    timeout_seconds: int = 300
    extra_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class BudgetConfig:
    monthly_budget_usd: float = 100.0
    quantum_time_seconds: int = 3600
    max_cost_per_task_usd: float = 1.0
    alert_threshold: float = 0.8
    auto_fallback_on_budget_exceeded: bool = True


@dataclass
class QuantumConfig:
    mode: ExecutionMode = ExecutionMode.LOCAL
    default_provider: ProviderType = ProviderType.LOCAL
    fallback_strategy: FallbackStrategy = FallbackStrategy.SIMULATED_ANNEALING
    providers: dict[ProviderType, ProviderConfig] = field(default_factory=dict)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    cache_results: bool = True
    log_level: str = "INFO"
    metrics_enabled: bool = False
    max_concurrent_tasks: int = 10
    retry_attempts: int = 3

    @classmethod
    def from_env(cls) -> QuantumConfig:
        return cls(
            mode=ExecutionMode(os.getenv("QUANTUM_MODE", "local")),
            default_provider=ProviderType(os.getenv("QUANTUM_PROVIDER", "local")),
            fallback_strategy=FallbackStrategy(
                os.getenv("QUANTUM_FALLBACK", "simulated_annealing")
            ),
            budget=BudgetConfig(
                monthly_budget_usd=float(os.getenv("QUANTUM_BUDGET_USD", "100")),
            ),
            log_level=os.getenv("QUANTUM_LOG_LEVEL", "INFO"),
        )

    @classmethod
    def for_local_development(cls) -> QuantumConfig:
        return cls(
            mode=ExecutionMode.LOCAL,
            default_provider=ProviderType.LOCAL,
            cache_results=True,
            log_level="DEBUG",
            metrics_enabled=False,
        )

    @classmethod
    def for_production(cls, budget_usd: float = 100.0) -> QuantumConfig:
        return cls(
            mode=ExecutionMode.PRODUCTION,
            default_provider=ProviderType.AWS_BRAKET,
            fallback_strategy=FallbackStrategy.SIMULATED_ANNEALING,
            budget=BudgetConfig(
                monthly_budget_usd=budget_usd,
                auto_fallback_on_budget_exceeded=True,
            ),
            cache_results=True,
            log_level="INFO",
            metrics_enabled=True,
        )

    def get_provider_config(self, provider: ProviderType) -> Optional[ProviderConfig]:
        return self.providers.get(provider)

    def is_production(self) -> bool:
        return self.mode in (ExecutionMode.PRODUCTION, ExecutionMode.HYBRID)
