"""
Tests for the command dispatcher.
"""

import pytest

from engines.hub.registry import ServiceRegistry
from engines.hub.dispatcher import Dispatcher


@pytest.fixture()
def registry(tmp_path):
    return ServiceRegistry(db_path=tmp_path / "test_dispatch.db")


@pytest.fixture()
def dispatcher(registry):
    return Dispatcher(registry)


class TestDispatcher:
    def test_dispatch_unknown_service(self, dispatcher):
        result = dispatcher.dispatch("nonexistent", "restart")
        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_call_service_unknown(self, dispatcher):
        result = dispatcher.call_service("nonexistent", "/status")
        assert result["status"] == "error"

    def test_find_service_for_capability(self, dispatcher, registry):
        registry.register(
            name="robot-arm",
            base_url="http://localhost:5000",
            capabilities=["motor_control", "sensor_read"],
        )
        svc = dispatcher.find_service_for_capability("motor_control")
        assert svc is not None
        assert svc["name"] == "robot-arm"

    def test_find_service_no_match(self, dispatcher, registry):
        registry.register(name="basic", base_url="http://x", capabilities=["logging"])
        assert dispatcher.find_service_for_capability("quantum_solve") is None

    def test_broadcast_empty(self, dispatcher):
        results = dispatcher.broadcast("ping")
        assert results == []

    def test_broadcast_with_filter(self, dispatcher, registry):
        registry.register(name="a", base_url="http://a", capabilities=["logging"])
        registry.register(name="b", base_url="http://b", capabilities=["metrics"])
        results = dispatcher.broadcast("collect", capability_filter="nonexistent")
        assert results == []
