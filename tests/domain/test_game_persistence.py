from sqlmodel import Session

from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
from ai_werewolf.storage.database import create_engine_and_tables, configured_database_url, normalize_database_url
from ai_werewolf.storage.repositories import GameRepository


def test_jdbc_postgres_url_is_normalized_for_sqlalchemy():
    url = normalize_database_url("jdbc:postgresql://127.0.0.1:5432/ai_werewolf")

    assert url == "postgresql+psycopg://127.0.0.1:5432/ai_werewolf"


def test_configured_database_url_uses_jdbc_environment(monkeypatch):
    monkeypatch.setenv("AI_WEREWOLF_JDBC_URL", "jdbc:postgresql://127.0.0.1:5432/ai_werewolf")
    monkeypatch.delenv("AI_WEREWOLF_DATABASE_URL", raising=False)

    assert configured_database_url() == "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ai_werewolf"


def test_game_repository_persists_game_and_player_roles():
    engine = create_engine_and_tables("sqlite:///:memory:")
    state = GameState(
        game_id="game_test",
        board_id="board_6_beginner",
        phase=GamePhase.SETUP,
        day_count=0,
        players=[
            PlayerState(player_id="human", agent_id=None, seat=1, role_key="seer", alive=True, is_human=True),
            PlayerState(player_id="agent_linye", agent_id="agent_linye", seat=2, role_key="werewolf", alive=True, is_human=False),
        ],
    )

    with Session(engine) as session:
        repository = GameRepository(session)
        repository.save_game(state, human_player_id="human", player_model_bindings={"human": "qwen", "agent_linye": "deepseek"})
        loaded = repository.get_game("game_test")

    assert loaded.game_id == "game_test"
    assert loaded.players[0].role_key == "seer"
    assert loaded.players[0].model_provider_id == "qwen"
    assert loaded.players[1].role_key == "werewolf"
    assert loaded.players[1].model_provider_id == "deepseek"
