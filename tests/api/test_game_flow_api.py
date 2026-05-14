from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def create_beginner_game(client: TestClient) -> dict:
    response = client.post(
        "/games",
        json={
            "board_id": "board_6_beginner",
            "human_player_id": "human",
            "agent_ids": ["agent_linye", "agent_xiaoman", "agent_qingshan", "agent_akai", "agent_moyu"],
        },
    )
    assert response.status_code == 200
    return response.json()


def post_action(client: TestClient, game_id: str, action_type: str, **extra) -> dict:
    response = client.post(
        f"/games/{game_id}/actions",
        json={
            "actor_player_id": "human",
            "action_type": action_type,
            "client_action_id": f"client-{action_type}",
            **extra,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_create_game_returns_persisted_frontend_game_state():
    client = TestClient(create_app())

    created = create_beginner_game(client)
    fetched = client.get(f"/games/{created['game_id']}")

    assert created["game_id"] != "game_pending"
    assert fetched.status_code == 200
    assert fetched.json()["game_id"] == created["game_id"]
    assert fetched.json()["phase"] == "setup"
    assert fetched.json()["human_player_id"] == "human"
    assert "allowed_actions" in fetched.json()
    assert fetched.json()["players"][0]["display_name"] == "你"


def test_game_flow_advances_through_mvp_phases():
    client = TestClient(create_app())
    game = create_beginner_game(client)
    game_id = game["game_id"]

    night = post_action(client, game_id, "start_game")
    announcement = post_action(client, game_id, "skip")
    speech = post_action(client, game_id, "continue")
    vote = post_action(client, game_id, "speech", content="我先听发言，今天重点看投票。")
    next_state = post_action(client, game_id, "vote", target_player_id="agent_linye")

    assert night["phase"] == "night"
    assert announcement["phase"] == "day_announcement"
    assert speech["phase"] == "day_speech"
    assert vote["phase"] == "day_vote"
    assert next_state["phase"] in {"night", "game_over"}
    assert next_state["day_count"] >= 1


def test_ai_roles_are_hidden_until_game_over():
    client = TestClient(create_app())
    game = create_beginner_game(client)

    ai_players = [player for player in game["players"] if player["is_human"] is False]
    human = next(player for player in game["players"] if player["is_human"] is True)

    assert human["role_key"] in {"werewolf", "seer", "villager"}
    assert all(player["role_key"] is None for player in ai_players)
