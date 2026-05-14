from fastapi.testclient import TestClient

from ai_werewolf.api.games import configure_game_repository
from ai_werewolf.main import create_app


class CapturingGameRepository:
    def __init__(self) -> None:
        self.saved = []

    def save_game(self, state, human_player_id, player_model_bindings):
        self.saved.append((state, human_player_id, player_model_bindings))


def test_create_game_persists_game_roles_and_model_bindings():
    repository = CapturingGameRepository()
    configure_game_repository(repository)
    client = TestClient(create_app())

    response = client.post(
        "/games",
        json={
            "board_id": "board_6_beginner",
            "human_player_id": "human",
            "agent_ids": ["agent_linye", "agent_xiaoman", "agent_qingshan", "agent_akai", "agent_moyu"],
        },
    )

    assert response.status_code == 200
    response_data = response.json()["data"]
    assert len(repository.saved) == 1
    state, human_player_id, player_model_bindings = repository.saved[0]
    assert state.game_id == response_data["game_id"]
    assert human_player_id == "human"
    assert set(player_model_bindings) == {player["player_id"] for player in response_data["players"]}
    assert all("model_provider_id" in player for player in response_data["players"])

    configure_game_repository(None)
