from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_list_boards_returns_array_for_frontend_editor():
    client = TestClient(create_app())

    response = client.get("/admin/boards")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
