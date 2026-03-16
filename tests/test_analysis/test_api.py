"""
Tests for Analysis API endpoints.
"""


class TestAnalysisAPI:
    def test_sonnet_endpoint_exists(self, client):
        resp = client.post(
            "/analysis/sonnet",
            json={"project_name": "TestProject"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_opus_endpoint_exists(self, client):
        resp = client.post(
            "/analysis/opus",
            json={
                "project_name": "TestProject",
                "sonnet_raw_response": "some sonnet output",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_full_endpoint_exists(self, client):
        resp = client.post(
            "/analysis/full",
            json={"project_name": "TestProject"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_name"] == "TestProject"
        assert "ai_architecture" in data

    def test_missing_project_name(self, client):
        resp = client.post("/analysis/full", json={})
        assert resp.status_code == 422
