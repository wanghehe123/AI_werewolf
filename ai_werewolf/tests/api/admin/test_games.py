from fastapi.testclient import TestClient


def login(client: TestClient) -> dict[str, str]:
    response = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    return {"session_id": response.json()["data"]["session_id"]}


def test_admin_games_list_requires_login(client: TestClient):
    response = client.get("/admin/games")

    assert response.status_code == 401
    assert response.json()["code"] == 401


def test_admin_games_list_after_login(client: TestClient):
    cookies = login(client)

    response = client.get("/admin/games", cookies=cookies)

    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert isinstance(response.json()["data"], list)
