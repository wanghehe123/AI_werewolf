from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_admin_can_create_board():
    client = TestClient(create_app())
    login = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    cookies = {"session_id": login.json()["data"]["session_id"]}
    payload = {
        "name": "后台配置板子",
        "description": "后台创建的测试板子",
        "min_players": 3,
        "max_players": 3,
        "sheriff_enabled": False,
        "enabled": True,
    }

    response = client.post("/admin/boards", json=payload, cookies=cookies)

    assert response.status_code == 201
    assert response.json()["code"] == 0
    assert response.json()["data"]["name"] == "后台配置板子"
