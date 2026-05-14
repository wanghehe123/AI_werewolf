from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_list_agents_returns_array_for_frontend_editor():
    client = TestClient(create_app())

    response = client.get("/admin/agents")

    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert isinstance(response.json()["data"], list)
