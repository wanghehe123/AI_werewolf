from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_player_lobby_lists_enabled_default_boards_and_agents():
    client = TestClient(create_app())

    boards_response = client.get("/boards")
    agents_response = client.get("/agents")

    assert boards_response.status_code == 200
    assert agents_response.status_code == 200
    assert any(board["board_id"] == "board_6_beginner" for board in boards_response.json())
    assert all(board["enabled"] is True for board in boards_response.json())
    assert len(agents_response.json()) >= 5
    assert all(agent["enabled"] is True for agent in agents_response.json())
