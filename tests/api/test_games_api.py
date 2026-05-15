from fastapi.testclient import TestClient

from ai_werewolf.api import games
from ai_werewolf.main import create_app


def test_create_game_requires_matching_agent_count():
    client = TestClient(create_app())

    response = client.post("/games", json={
        "board_id": "board_6_beginner",
        "human_player_id": "human",
        "agent_ids": ["agent_linye"],
    })

    assert response.status_code == 400
    assert response.json()["code"] == 400
    assert "agent count" in response.json()["message"]


def test_create_game_accepts_human_role_key_for_testing():
    client = TestClient(create_app())

    response = client.post("/games", json={
        "board_id": "board_6_beginner",
        "human_player_id": "human",
        "human_role_key": "seer",
        "agent_ids": ["agent_linye", "agent_xiaoman", "agent_qingshan", "agent_akai", "agent_moyu"],
    })

    assert response.status_code == 200
    human = next(player for player in response.json()["data"]["players"] if player["is_human"])
    assert human["role_key"] == "seer"


def test_create_game_rejects_unavailable_human_role_key():
    client = TestClient(create_app())

    response = client.post("/games", json={
        "board_id": "board_6_beginner",
        "human_player_id": "human",
        "human_role_key": "witch",
        "agent_ids": ["agent_linye", "agent_xiaoman", "agent_qingshan", "agent_akai", "agent_moyu"],
    })

    assert response.status_code == 400
    assert "fixed role witch is not available" in response.json()["message"]


def test_game_stream_replays_events_after_last_event_id():
    client = TestClient(create_app())
    created = client.post(
        "/games",
        json={
            "board_id": "board_6_beginner",
            "human_player_id": "human",
            "agent_ids": ["agent_linye", "agent_xiaoman", "agent_qingshan", "agent_akai", "agent_moyu"],
        },
    ).json()["data"]
    game_id = created["game_id"]

    session = games._get_session(game_id)
    first_event_id = session.stream_events[0]["event_id"]
    client.post(
        f"/games/{game_id}/actions",
        json={
            "actor_player_id": "human",
            "action_type": "start_game",
            "client_action_id": "client-start",
        },
    )

    replayed = list(games.replay_stream_events(session, first_event_id))

    assert replayed
    assert replayed[0]["event_type"] == "phase_changed"
    assert replayed[0]["payload"]["message"] == "夜幕降临，所有玩家闭眼。"


def test_game_stream_snapshot_event_contains_frontend_state():
    client = TestClient(create_app())
    created = client.post(
        "/games",
        json={
            "board_id": "board_6_beginner",
            "human_player_id": "human",
            "agent_ids": ["agent_linye", "agent_xiaoman", "agent_qingshan", "agent_akai", "agent_moyu"],
        },
    ).json()["data"]

    snapshot = games.build_state_snapshot_event(games._get_session(created["game_id"]))

    assert snapshot["event_type"] == "state_snapshot"
    assert snapshot["game_id"] == created["game_id"]
    assert snapshot["payload"]["game_state"]["game_id"] == created["game_id"]
