from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_list_agents_returns_array_for_frontend_editor():
    client = TestClient(create_app())
    login = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    cookies = {"session_id": login.json()["data"]["session_id"]}

    response = client.get("/admin/agents", cookies=cookies)

    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert isinstance(response.json()["data"], list)
