"""
Tests for the main FastAPI app.
"""


class TestMainApp:
    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Software Engines"
        assert "persona" in data["engines"]
        assert "hub" in data["engines"]
        assert "analysis" in data["engines"]
        assert "quantum" in data["engines"]

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_docs_available(self, client):
        resp = client.get("/docs")
        assert resp.status_code == 200
