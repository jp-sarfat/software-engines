"""
Tests for budget manager.
"""

from engines.quantum.budget import BudgetManager
from engines.quantum.config import BudgetConfig


class TestBudgetManager:
    def setup_method(self):
        self.mgr = BudgetManager(BudgetConfig(monthly_budget_usd=100, quantum_time_seconds=3600))

    def test_initial_state(self):
        assert self.mgr.remaining_usd == 100.0
        assert self.mgr.remaining_time_seconds == 3600.0
        assert self.mgr.usage_percentage == 0.0

    def test_can_execute(self):
        assert self.mgr.can_execute()
        assert self.mgr.can_execute(estimated_cost_usd=0.5)

    def test_cannot_exceed_budget(self):
        assert not self.mgr.can_execute(estimated_cost_usd=200)

    def test_record_usage(self):
        self.mgr.record_usage(10, 60)
        assert self.mgr.remaining_usd == 90.0
        assert self.mgr.remaining_time_seconds == 3540.0

    def test_reset(self):
        self.mgr.record_usage(50, 1800)
        self.mgr.reset()
        assert self.mgr.remaining_usd == 100.0
        assert self.mgr.usage_percentage == 0.0

    def test_usage_report(self):
        self.mgr.record_usage(5, 30, provider="local", problem_name="test")
        report = self.mgr.get_usage_report()
        assert report["task_count"] == 1
        assert report["total_cost_usd"] == 5.0

    def test_per_task_limit(self):
        mgr = BudgetManager(BudgetConfig(max_cost_per_task_usd=0.5))
        assert not mgr.can_execute(estimated_cost_usd=1.0)
