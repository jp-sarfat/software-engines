"""
Tests for the service registry.
"""

import pytest

from engines.hub.registry import ServiceRegistry


@pytest.fixture()
def registry(tmp_path):
    return ServiceRegistry(db_path=tmp_path / "test_hub.db")


class TestServiceCRUD:
    def test_register_service(self, registry):
        result = registry.register(
            name="robotics",
            base_url="http://localhost:3000",
            description="Robotics control API",
            capabilities=["motor_control", "sensor_read"],
        )
        assert "service_id" in result
        assert "hub_token" in result
        assert len(result["hub_token"]) > 20

    def test_get_service(self, registry):
        registry.register(name="test-svc", base_url="http://localhost:4000")
        svc = registry.get_service_by_name("test-svc")
        assert svc is not None
        assert svc["name"] == "test-svc"
        assert svc["base_url"] == "http://localhost:4000"
        assert svc["status"] == "registered"

    def test_list_services(self, registry):
        registry.register(name="svc-a", base_url="http://a")
        registry.register(name="svc-b", base_url="http://b")
        services = registry.list_services()
        assert len(services) == 2

    def test_update_service(self, registry):
        registry.register(name="updatable", base_url="http://old")
        ok = registry.update_service("updatable", base_url="http://new", version="2.0")
        assert ok is True
        svc = registry.get_service_by_name("updatable")
        assert svc["base_url"] == "http://new"
        assert svc["version"] == "2.0"

    def test_unregister_service(self, registry):
        registry.register(name="to-remove", base_url="http://x")
        assert registry.unregister("to-remove") is True
        assert registry.get_service_by_name("to-remove") is None

    def test_unregister_nonexistent(self, registry):
        assert registry.unregister("nope") is False

    def test_register_updates_on_conflict(self, registry):
        registry.register(name="dup", base_url="http://v1", description="old")
        registry.register(name="dup", base_url="http://v2", description="new")
        svc = registry.get_service_by_name("dup")
        assert svc["base_url"] == "http://v2"
        assert svc["description"] == "new"

    def test_capabilities_stored_as_list(self, registry):
        registry.register(name="cap-svc", base_url="http://x", capabilities=["a", "b", "c"])
        svc = registry.get_service_by_name("cap-svc")
        assert svc["capabilities"] == ["a", "b", "c"]

    def test_metadata_stored(self, registry):
        registry.register(name="meta", base_url="http://x", metadata={"env": "prod", "port": 8080})
        svc = registry.get_service_by_name("meta")
        assert svc["metadata"]["env"] == "prod"

    def test_validate_hub_token(self, registry):
        result = registry.register(name="auth-svc", base_url="http://x")
        token = result["hub_token"]
        assert registry.validate_hub_token("auth-svc", token) is True
        assert registry.validate_hub_token("auth-svc", "wrong-token") is False
        assert registry.validate_hub_token("nonexistent", token) is False


class TestEvents:
    def test_record_event(self, registry):
        result = registry.register(name="evt-svc", base_url="http://x")
        svc = registry.get_service_by_name("evt-svc")
        eid = registry.record_event(svc["id"], "deploy", severity="info", payload={"version": "1.0"})
        assert isinstance(eid, int)

    def test_get_events(self, registry):
        result = registry.register(name="evt-svc2", base_url="http://x")
        svc = registry.get_service_by_name("evt-svc2")
        registry.record_event(svc["id"], "deploy")
        registry.record_event(svc["id"], "error", severity="error")
        events = registry.get_events(service_id=svc["id"])
        assert len(events) == 2

    def test_get_events_by_type(self, registry):
        result = registry.register(name="type-svc", base_url="http://x")
        svc = registry.get_service_by_name("type-svc")
        registry.record_event(svc["id"], "deploy")
        registry.record_event(svc["id"], "error")
        events = registry.get_events(event_type="error")
        assert len(events) == 1
        assert events[0]["event_type"] == "error"

    def test_unprocessed_events(self, registry):
        result = registry.register(name="unp-svc", base_url="http://x")
        svc = registry.get_service_by_name("unp-svc")
        eid = registry.record_event(svc["id"], "alert")
        unprocessed = registry.get_unprocessed_events()
        assert len(unprocessed) >= 1

    def test_mark_processed(self, registry):
        result = registry.register(name="proc-svc", base_url="http://x")
        svc = registry.get_service_by_name("proc-svc")
        eid = registry.record_event(svc["id"], "alert")
        assert registry.mark_event_processed(eid) is True
        unprocessed = registry.get_unprocessed_events()
        assert all(e["id"] != eid for e in unprocessed)


class TestCommands:
    def test_create_command(self, registry):
        registry.register(name="cmd-svc", base_url="http://x")
        svc = registry.get_service_by_name("cmd-svc")
        cid = registry.create_command(svc["id"], "restart", payload={"force": True})
        assert isinstance(cid, int)

    def test_update_command_status(self, registry):
        registry.register(name="cmd-svc2", base_url="http://x")
        svc = registry.get_service_by_name("cmd-svc2")
        cid = registry.create_command(svc["id"], "deploy")
        assert registry.update_command_status(cid, "success", response="OK") is True
        cmds = registry.get_commands(service_id=svc["id"])
        assert cmds[0]["status"] == "success"

    def test_get_commands_by_status(self, registry):
        registry.register(name="cmd-svc3", base_url="http://x")
        svc = registry.get_service_by_name("cmd-svc3")
        cid1 = registry.create_command(svc["id"], "task1")
        cid2 = registry.create_command(svc["id"], "task2")
        registry.update_command_status(cid1, "success")
        pending = registry.get_commands(status="pending")
        assert all(c["status"] == "pending" for c in pending)


class TestStats:
    def test_empty_stats(self, registry):
        stats = registry.get_stats()
        assert stats["total_services"] == 0
        assert stats["total_events"] == 0

    def test_populated_stats(self, registry):
        registry.register(name="stat-svc", base_url="http://x")
        svc = registry.get_service_by_name("stat-svc")
        registry.record_event(svc["id"], "deploy")
        registry.create_command(svc["id"], "restart")
        stats = registry.get_stats()
        assert stats["total_services"] == 1
        assert stats["total_events"] == 1
        assert stats["total_commands"] == 1
