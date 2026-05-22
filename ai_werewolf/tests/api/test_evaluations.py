from fastapi.testclient import TestClient
from sqlmodel import Session

from ai_werewolf.api.admin import dependencies
from ai_werewolf.main import create_app
from ai_werewolf.storage.admin_repository import AgentRepository, BoardRepository, PlayerRepository


def _reset_admin_engine() -> None:
    dependencies._admin_engine = None


def test_ai_game_evaluation_requires_database(monkeypatch):
    monkeypatch.setenv("AI_WEREWOLF_DATABASE_ENABLED", "false")
    _reset_admin_engine()

    with TestClient(create_app()) as client:
        response = client.post("/evaluations/ai-games/run", json={"board_id": "b1"})

    assert response.status_code == 503
    assert "database" in response.json()["message"].lower()


def test_ai_game_evaluation_selects_ai_players_and_runs(monkeypatch, tmp_path):
    database_url = f"sqlite:///{tmp_path / 'eval.db'}"
    monkeypatch.setenv("AI_WEREWOLF_DATABASE_ENABLED", "true")
    monkeypatch.setenv("AI_WEREWOLF_DATABASE_URL", database_url)
    _reset_admin_engine()

    with TestClient(create_app()) as client:
        with Session(dependencies.admin_engine()) as session:
            board_repo = BoardRepository(session)
            board = board_repo.create(
                name="评测 3 人板",
                min_players=3,
                max_players=3,
                sheriff_enabled=False,
                enabled=True,
            )
            board_id = board.board_id
            board_repo.replace_roles(
                board_id,
                [
                    {"role_key": "werewolf", "count": 1},
                    {"role_key": "seer", "count": 1},
                    {"role_key": "villager", "count": 1},
                ],
            )
            agent_repo = AgentRepository(session)
            player_repo = PlayerRepository(session)
            for index in range(3):
                agent = agent_repo.create(
                    name=f"AI-{index}",
                    persona="冷静",
                    speech_style="简短",
                    agent_id=f"agent-{index}",
                    enabled=True,
                )
                player_repo.create(name=f"玩家-{index}", is_ai=True, agent_id=agent.agent_id)

        def fake_run(session, orchestrator, *, max_steps):
            session.state.winner = "villagers"
            return {"status": "game_over", "steps": 2, "winner": "villagers", "error": None}

        monkeypatch.setattr("ai_werewolf.api.evaluations.run_ai_game_until_done", fake_run)
        response = client.post(
            "/evaluations/ai-games/run",
            json={"board_id": board_id, "seed": 7, "max_steps": 5},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "game_over"
    assert data["winner"] == "villagers"
    assert data["steps"] == 2
    assert data["game_id"].startswith("eval_")
    assert data["artifacts"]["stream_url"] == f"/games/{data['game_id']}/stream"
    assert data["artifacts"]["prompt_trace_dir"] == f"logs/prompt_traces/{data['game_id']}"
    assert len(data["players"]) == 3
    assert {player["is_human"] for player in data["players"]} == {False}
