"""
Tests for Quantum API endpoints.
"""


class TestQuantumAPI:
    def test_status(self, client):
        resp = client.get("/quantum/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "local"

    def test_solve_qubo(self, client):
        resp = client.post(
            "/quantum/solve/qubo",
            json={
                "name": "API QUBO",
                "qubo_matrix": [[-1, 2], [2, -1]],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["solution"] is not None
        assert data["solver_type"] is not None

    def test_solve_maxcut(self, client):
        resp = client.post(
            "/quantum/solve/maxcut",
            json={
                "name": "API MaxCut",
                "edges": [[0, 1], [1, 2], [2, 0]],
                "num_nodes": 3,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    def test_solve_tsp(self, client):
        resp = client.post(
            "/quantum/solve/tsp",
            json={
                "name": "API TSP",
                "distance_matrix": [[0, 10], [10, 0]],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    def test_reset_budget(self, client):
        resp = client.post("/quantum/reset-budget")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
