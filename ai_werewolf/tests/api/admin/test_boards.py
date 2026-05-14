from fastapi.testclient import TestClient


def login(client: TestClient) -> dict[str, str]:
    response = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    return {"session_id": response.json()["data"]["session_id"]}


def test_admin_board_create_and_replace_roles(client: TestClient):
    cookies = login(client)

    created = client.post(
        "/admin/boards",
        json={
            "name": "6人新手局后台版",
            "description": "2狼1预3民",
            "min_players": 6,
            "max_players": 6,
            "sheriff_enabled": False,
            "enabled": True,
        },
        cookies=cookies,
    )
    assert created.status_code == 201
    board = created.json()["data"]

    roles = client.put(
        f"/admin/boards/{board['board_id']}/roles",
        json={
            "roles": [
                {"role_key": "werewolf", "count": 2},
                {"role_key": "seer", "count": 1},
                {"role_key": "villager", "count": 3},
            ]
        },
        cookies=cookies,
    )

    assert roles.json()["code"] == 0
    assert sum(item["count"] for item in roles.json()["data"]) == 6

    detail = client.get(f"/admin/boards/{board['board_id']}", cookies=cookies)
    assert len(detail.json()["data"]["roles"]) == 3

    updated = client.put(f"/admin/boards/{board['board_id']}", json={"enabled": False}, cookies=cookies)
    assert updated.json()["data"]["enabled"] is False

    deleted = client.delete(f"/admin/boards/{board['board_id']}", cookies=cookies)
    assert deleted.json()["code"] == 0
