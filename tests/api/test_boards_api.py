from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_admin_can_create_board():
    client = TestClient(create_app())
    payload = {
        "board_id": "board_custom",
        "name": "后台配置板子",
        "roles": [
            {"role_key": "werewolf", "count": 1},
            {"role_key": "villager", "count": 2},
        ],
        "sheriff_enabled": False,
        "speech_rule": "seat_order",
        "vote_rule": "single_vote",
        "win_condition": "wolves_eliminated_or_parity",
        "enabled": True,
    }

    response = client.post("/admin/boards", json=payload)

    assert response.status_code == 201
    assert response.json()["board_id"] == "board_custom"
