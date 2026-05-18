from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_health_endpoint():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"code": 0, "message": "ok", "data": {"status": "ok"}}


def test_health_endpoint_allows_localhost_vite_cors_origin():
    client = TestClient(create_app())

    response = client.get("/health", headers={"Origin": "http://localhost:5175"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5175"
    assert response.headers["access-control-allow-credentials"] == "true"
