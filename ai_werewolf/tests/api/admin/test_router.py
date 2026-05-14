from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_admin_session_route_is_registered():
    client = TestClient(create_app())

    response = client.get("/admin/session")

    assert response.status_code == 200
    assert response.json()["code"] == 401


def test_protected_admin_route_returns_401_without_session():
    client = TestClient(create_app())

    response = client.get("/admin/players")

    assert response.status_code == 401
    assert response.json()["code"] == 401
