from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_create_game_uses_unified_response_format():
    client = TestClient(create_app())

    response = client.post(
        "/games",
        json={
            "board_id": "board_6_beginner",
            "human_player_id": "human",
            "agent_ids": ["agent_linye", "agent_xiaoman", "agent_qingshan", "agent_akai", "agent_moyu"],
        },
    )

    body = response.json()

    assert response.status_code == 200
    assert body["code"] == 0
    assert body["message"] == "ok"
    assert body["data"]["game_id"].startswith("game_")


def test_game_error_uses_unified_response_format():
    client = TestClient(create_app())

    response = client.post(
        "/games",
        json={
            "board_id": "board_6_beginner",
            "human_player_id": "human",
            "agent_ids": ["agent_linye"],
        },
    )

    body = response.json()

    assert response.status_code == 400
    assert body["code"] == 400
    assert "agent count" in body["message"]
    assert body["data"] is None
