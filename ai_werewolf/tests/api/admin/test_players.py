import logging

from fastapi.testclient import TestClient


def login(client: TestClient) -> dict[str, str]:
    response = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    return {"session_id": response.json()["data"]["session_id"]}


def test_admin_player_crud(client: TestClient):
    cookies = login(client)

    created = client.post("/admin/players", json={"name": "测试玩家-players", "is_ai": False}, cookies=cookies)
    assert created.status_code == 201
    player = created.json()["data"]
    assert player["name"] == "测试玩家-players"
    assert player["is_ai"] is False

    detail = client.get(f"/admin/players/{player['player_id']}", cookies=cookies)
    assert detail.json()["data"]["player_id"] == player["player_id"]

    listed = client.get("/admin/players", cookies=cookies)
    assert any(item["player_id"] == player["player_id"] for item in listed.json()["data"])

    updated = client.put(f"/admin/players/{player['player_id']}", json={"name": "新名字-players"}, cookies=cookies)
    assert updated.json()["data"]["name"] == "新名字-players"

    deleted = client.delete(f"/admin/players/{player['player_id']}", cookies=cookies)
    assert deleted.json()["code"] == 0


def test_admin_player_requests_log_database_target(client: TestClient, caplog):
    cookies = login(client)

    caplog.set_level(logging.INFO, logger="ai_werewolf.api.admin.dependencies")
    caplog.set_level(logging.INFO, logger="ai_werewolf.storage.admin_repository")

    created = client.post("/admin/players", json={"name": "日志测试玩家", "is_ai": False}, cookies=cookies)
    listed = client.get("/admin/players", cookies=cookies)

    assert created.status_code == 201
    assert listed.status_code == 200
    assert "admin database session opened" in caplog.text
    assert "admin.players.create committed" in caplog.text
    assert "db=sqlite://" in caplog.text
