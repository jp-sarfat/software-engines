"""
Budget manager for quantum resource usage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from engines.quantum.config import BudgetConfig

logger = logging.getLogger(__name__)


@dataclass
class UsageRecord:
    timestamp: datetime
    cost_usd: float
    time_seconds: float
    provider: str
    problem_name: str


class BudgetManager:
    def __init__(self, config: BudgetConfig):
        self.config = config
        self._total_cost_usd: float = 0.0
        self._total_time_seconds: float = 0.0
        self._history: list[UsageRecord] = []
        self._period_start = datetime.now(timezone.utc)
        self._alert_sent = False

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.config.monthly_budget_usd - self._total_cost_usd)

    @property
    def remaining_time_seconds(self) -> float:
        return max(0.0, self.config.quantum_time_seconds - self._total_time_seconds)

    @property
    def usage_percentage(self) -> float:
        cost_pct = (
            self._total_cost_usd / self.config.monthly_budget_usd
            if self.config.monthly_budget_usd > 0
            else 0
        )
        time_pct = (
            self._total_time_seconds / self.config.quantum_time_seconds
            if self.config.quantum_time_seconds > 0
            else 0
        )
        return max(cost_pct, time_pct) * 100

    def can_execute(self, estimated_cost_usd: float = 0.0) -> bool:
        if self._total_cost_usd + estimated_cost_usd > self.config.monthly_budget_usd:
            return False
        if self._total_time_seconds >= self.config.quantum_time_seconds:
            return False
        if estimated_cost_usd > self.config.max_cost_per_task_usd:
            return False
        return True

    def record_usage(
        self,
        cost_usd: float,
        time_seconds: float,
        provider: str = "unknown",
        problem_name: str = "",
    ) -> None:
        self._total_cost_usd += cost_usd
        self._total_time_seconds += time_seconds
        self._history.append(
            UsageRecord(datetime.now(timezone.utc), cost_usd, time_seconds, provider, problem_name)
        )
        self._check_alerts()

    def _check_alerts(self) -> None:
        if self._alert_sent:
            return
        if self.usage_percentage >= self.config.alert_threshold * 100:
            logger.warning(
                "Budget alert: %.1f%% used. Remaining: $%.2f, %.0fs",
                self.usage_percentage,
                self.remaining_usd,
                self.remaining_time_seconds,
            )
            self._alert_sent = True

    def reset(self) -> None:
        self._total_cost_usd = 0.0
        self._total_time_seconds = 0.0
        self._history.clear()
        self._period_start = datetime.now(timezone.utc)
        self._alert_sent = False

    def get_usage_report(self) -> dict[str, Any]:
        return {
            "period_start": self._period_start.isoformat(),
            "total_cost_usd": self._total_cost_usd,
            "total_time_seconds": self._total_time_seconds,
            "remaining_cost_usd": self.remaining_usd,
            "remaining_time_seconds": self.remaining_time_seconds,
            "usage_percentage": self.usage_percentage,
            "task_count": len(self._history),
        }
