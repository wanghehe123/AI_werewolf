from fastapi.testclient import TestClient


def _login(client: TestClient) -> dict[str, str]:
    response = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    return {"session_id": response.json()["data"]["session_id"]}


def test_create_complete_board_with_roles(client: TestClient):
    """Creating a board via /admin/boards/complete returns the board with roles populated."""
    cookies = _login(client)

    payload = {
        "name": "8人预女猎",
        "description": "标准预女猎守卫配置",
        "min_players": 8,
        "max_players": 8,
        "sheriff_enabled": True,
        "enabled": True,
        "roles": [
            {"role_key": "werewolf", "count": 2},
            {"role_key": "seer", "count": 1},
            {"role_key": "witch", "count": 1},
            {"role_key": "hunter", "count": 1},
            {"role_key": "villager", "count": 3},
        ],
    }

    response = client.post("/admin/boards/complete", json=payload, cookies=cookies)
    assert response.status_code == 201
    data = response.json()["data"]

    assert data["name"] == "8人预女猎"
    assert data["sheriff_enabled"] is True
    assert data["enabled"] is True
    assert len(data["roles"]) == 5
    assert sum(item["count"] for item in data["roles"]) == 8

    # Verify it is retrievable
    detail = client.get(f"/admin/boards/{data['board_id']}", cookies=cookies)
    assert len(detail.json()["data"]["roles"]) == 5


def test_create_complete_board_roles_out_of_range(client: TestClient):
    """Returns 400 when total role count is outside [min_players, max_players]."""
    cookies = _login(client)

    payload = {
        "name": "测试局",
        "min_players": 6,
        "max_players": 8,
        "sheriff_enabled": False,
        "enabled": True,
        "roles": [
            {"role_key": "werewolf", "count": 1},
            {"role_key": "villager", "count": 2},
        ],
    }

    response = client.post("/admin/boards/complete", json=payload, cookies=cookies)
    assert response.status_code == 400
    assert "role total" in response.json()["message"].lower()


def test_create_complete_board_unknown_role(client: TestClient):
    """Returns 400 when a role_key is not in BuiltInRoleRegistry."""
    cookies = _login(client)

    payload = {
        "name": "未知角色局",
        "min_players": 3,
        "max_players": 3,
        "sheriff_enabled": False,
        "enabled": True,
        "roles": [
            {"role_key": "werewolf", "count": 1},
            {"role_key": "alien", "count": 2},
        ],
    }

    response = client.post("/admin/boards/complete", json=payload, cookies=cookies)
    assert response.status_code == 400
    assert "unknown role" in response.json()["message"].lower()


def test_create_complete_board_min_gt_max(client: TestClient):
    """Returns 400 when min_players > max_players."""
    cookies = _login(client)

    payload = {
        "name": "非法局",
        "min_players": 10,
        "max_players": 5,
        "sheriff_enabled": False,
        "enabled": True,
        "roles": [
            {"role_key": "werewolf", "count": 2},
            {"role_key": "villager", "count": 3},
        ],
    }

    response = client.post("/admin/boards/complete", json=payload, cookies=cookies)
    assert response.status_code == 400
    assert "min_players" in response.json()["message"].lower()
