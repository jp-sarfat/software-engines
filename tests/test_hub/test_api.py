"""
Tests for the Hub API endpoints.
"""


class TestHubStatus:
    def test_status(self, client):
        resp = client.get("/hub/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_services" in data
        assert "services" in data

    def test_health_check_all(self, client):
        resp = client.get("/hub/health")
        assert resp.status_code == 200
        assert "results" in resp.json()


class TestServiceManagement:
    def test_register_service(self, client):
        resp = client.post("/hub/services/register", json={
            "name": "test-robotics",
            "base_url": "http://localhost:3000",
            "description": "Robotics API",
            "capabilities": ["motor_control", "sensor_read"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "registered"
        assert "hub_token" in data
        assert "service_id" in data

    def test_list_services(self, client):
        client.post("/hub/services/register", json={
            "name": "list-test",
            "base_url": "http://localhost:4000",
        })
        resp = client.get("/hub/services")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_service(self, client):
        client.post("/hub/services/register", json={
            "name": "get-test",
            "base_url": "http://localhost:5000",
        })
        resp = client.get("/hub/services/get-test")
        assert resp.status_code == 200
        assert resp.json()["name"] == "get-test"

    def test_get_service_not_found(self, client):
        resp = client.get("/hub/services/nonexistent-xyz")
        assert resp.status_code == 404

    def test_update_service(self, client):
        client.post("/hub/services/register", json={
            "name": "update-test",
            "base_url": "http://localhost:6000",
        })
        resp = client.put("/hub/services/update-test", json={
            "description": "Updated description",
            "version": "2.0",
        })
        assert resp.status_code == 200
        svc = client.get("/hub/services/update-test").json()
        assert svc["description"] == "Updated description"

    def test_delete_service(self, client):
        client.post("/hub/services/register", json={
            "name": "delete-test",
            "base_url": "http://localhost:7000",
        })
        resp = client.delete("/hub/services/delete-test")
        assert resp.status_code == 200
        assert client.get("/hub/services/delete-test").status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/hub/services/nonexistent-xyz")
        assert resp.status_code == 404

    def test_health_check_not_found(self, client):
        resp = client.get("/hub/services/nonexistent-xyz/health")
        assert resp.status_code == 404


class TestEvents:
    def _register(self, client, name="evt-svc"):
        client.post("/hub/services/register", json={
            "name": name,
            "base_url": "http://localhost:8001",
        })

    def test_push_event(self, client):
        self._register(client, "push-evt")
        resp = client.post("/hub/events", json={
            "service_name": "push-evt",
            "event_type": "deploy_complete",
            "severity": "info",
            "payload": {"version": "1.2.0"},
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "recorded"

    def test_push_event_unknown_service(self, client):
        resp = client.post("/hub/events", json={
            "service_name": "nonexistent",
            "event_type": "test",
        })
        assert resp.status_code == 404

    def test_list_events(self, client):
        self._register(client, "list-evt")
        client.post("/hub/events", json={
            "service_name": "list-evt",
            "event_type": "test_event",
        })
        resp = client.get("/hub/events")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_unprocessed_events(self, client):
        resp = client.get("/hub/events/unprocessed")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_mark_processed_not_found(self, client):
        resp = client.post("/hub/events/99999/processed")
        assert resp.status_code == 404


class TestCommands:
    def _register(self, client, name="cmd-svc"):
        client.post("/hub/services/register", json={
            "name": name,
            "base_url": "http://localhost:9001",
        })

    def test_dispatch_to_unknown(self, client):
        resp = client.post("/hub/commands/dispatch", json={
            "service_name": "nonexistent",
            "command": "restart",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_dispatch_creates_command(self, client):
        self._register(client, "dispatch-svc")
        resp = client.post("/hub/commands/dispatch", json={
            "service_name": "dispatch-svc",
            "command": "restart",
            "path": "/restart",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("success", "failed", "error", "timeout")

    def test_broadcast(self, client):
        resp = client.post("/hub/commands/broadcast", json={
            "command": "ping",
        })
        assert resp.status_code == 200
        assert "results" in resp.json()

    def test_list_commands(self, client):
        resp = client.get("/hub/commands")
        assert resp.status_code == 200

    def test_route_no_capability(self, client):
        resp = client.post("/hub/route?capability=nonexistent_cap")
        assert resp.status_code == 404
