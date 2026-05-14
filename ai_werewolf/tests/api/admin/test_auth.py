import pytest
from fastapi.testclient import TestClient


def test_login_success(client: TestClient):
    response = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "session_id" in data["data"]


def test_login_failure(client: TestClient):
    response = client.post("/admin/login", params={"username": "wrong", "password": "wrong"})
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 1
    assert "error" in data["message"].lower() or "密码" in data["message"]


def test_check_session_authenticated(client: TestClient):
    # Login first
    login_resp = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    session_id = login_resp.json()["data"]["session_id"]
    # Check session
    response = client.get("/admin/session", cookies={"session_id": session_id})
    assert response.status_code == 200
    assert response.json()["code"] == 0


def test_check_session_not_authenticated(client: TestClient):
    response = client.get("/admin/session")
    assert response.status_code == 200
    assert response.json()["code"] == 401