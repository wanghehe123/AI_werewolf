from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_create_game_requires_matching_agent_count():
    client = TestClient(create_app())

    response = client.post("/games", json={
        "board_id": "board_6_beginner",
        "human_player_id": "human",
        "agent_ids": ["agent_linye"],
    })

    assert response.status_code == 400
    assert "agent count" in response.json()["detail"]
