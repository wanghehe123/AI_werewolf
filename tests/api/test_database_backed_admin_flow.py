from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from ai_werewolf.api.admin import dependencies as admin_dependencies
from ai_werewolf.llm.model_config import load_llm_config_from_yaml
from ai_werewolf.main import create_app
from ai_werewolf.storage.database import create_engine_and_tables
from ai_werewolf.storage.models import LLMProviderRecord, RoleModelBindingRecord


def _client_with_sqlite_database(monkeypatch, tmp_path: Path) -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'admin-flow.db'}"
    monkeypatch.setenv("AI_WEREWOLF_DATABASE_ENABLED", "true")
    monkeypatch.setenv("AI_WEREWOLF_DATABASE_URL", database_url)
    admin_dependencies._admin_engine = None
    return TestClient(create_app())


def _login(client: TestClient) -> dict[str, str]:
    response = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    return {"session_id": response.json()["data"]["session_id"]}


def test_player_lobby_and_game_creation_use_database_configured_boards_and_agents(monkeypatch, tmp_path: Path):
    client = _client_with_sqlite_database(monkeypatch, tmp_path)
    cookies = _login(client)

    client.post("/admin/roles/seed", cookies=cookies)
    board_response = client.post(
        "/admin/boards",
        json={
            "name": "数据库2人测试局",
            "description": "后台配置生成",
            "min_players": 2,
            "max_players": 2,
            "sheriff_enabled": False,
            "enabled": True,
        },
        cookies=cookies,
    )
    board_id = board_response.json()["data"]["board_id"]
    client.put(
        f"/admin/boards/{board_id}/roles",
        json={"roles": [{"role_key": "werewolf", "count": 1}, {"role_key": "villager", "count": 1}]},
        cookies=cookies,
    )
    agent_response = client.post(
        "/admin/agents",
        json={
            "agent_id": "db_agent_one",
            "name": "数据库玩家",
            "persona": "只从数据库读取的人设",
            "speech_style": "短句",
            "reasoning_level": 3,
            "deception_level": 3,
            "aggression_level": 3,
            "cooperation_level": 3,
            "risk_preference": "balanced",
            "memory_style": "focus_on_votes",
            "enabled": True,
        },
        cookies=cookies,
    )
    agent_id = agent_response.json()["data"]["agent_id"]
    provider_response = client.post(
        "/admin/llm/providers",
        json={"provider_id": "db_fake", "provider_type": "fake", "model_name": "fake-default"},
        cookies=cookies,
    )
    assert provider_response.status_code == 201
    binding_response = client.post(
        "/admin/llm/role-bindings",
        json={"role_key": "werewolf", "provider_id": "db_fake"},
        cookies=cookies,
    )
    assert binding_response.status_code == 201

    lobby_boards = client.get("/boards").json()["data"]
    lobby_agents = client.get("/agents").json()["data"]
    game_response = client.post(
        "/games",
        json={"board_id": board_id, "human_player_id": "human", "agent_ids": [agent_id]},
    )

    assert any(board["board_id"] == board_id and board["name"] == "数据库2人测试局" for board in lobby_boards)
    assert any(agent["agent_id"] == agent_id and agent["name"] == "数据库玩家" for agent in lobby_agents)
    assert game_response.status_code == 200
    assert game_response.json()["data"]["board_id"] == board_id
    assert any(player["agent_id"] == agent_id for player in game_response.json()["data"]["players"])


def test_admin_llm_provider_and_role_binding_are_persisted_to_database(monkeypatch, tmp_path: Path):
    client = _client_with_sqlite_database(monkeypatch, tmp_path)
    cookies = _login(client)

    provider_response = client.post(
        "/admin/llm/providers",
        json={
            "provider_id": "db_deepseek",
            "provider_type": "openai_compatible",
            "model_name": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "DEEPSEEK_API_KEY",
        },
        cookies=cookies,
    )
    binding_response = client.post(
        "/admin/llm/role-bindings",
        json={"role_key": "werewolf", "provider_id": "db_deepseek"},
        cookies=cookies,
    )

    engine = create_engine_and_tables(f"sqlite:///{tmp_path / 'admin-flow.db'}")
    with Session(engine) as session:
        provider = session.get(LLMProviderRecord, "db_deepseek")
        binding = session.exec(
            select(RoleModelBindingRecord).where(RoleModelBindingRecord.role_key == "werewolf")
        ).first()

    assert provider_response.status_code == 201
    assert binding_response.status_code == 201
    assert provider is not None
    assert provider.model_name == "deepseek-chat"
    assert binding is not None
    assert binding.provider_id == "db_deepseek"


def test_game_engine_prefers_yaml_llm_config_on_startup(monkeypatch, tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'startup-llm.db'}"
    monkeypatch.setenv("AI_WEREWOLF_DATABASE_ENABLED", "true")
    monkeypatch.setenv("AI_WEREWOLF_DATABASE_URL", database_url)
    admin_dependencies._admin_engine = None

    engine = create_engine_and_tables(database_url)
    with Session(engine) as session:
        session.merge(
            LLMProviderRecord(
                provider_id="db_deepseek",
                provider_type="openai_compatible",
                model_name="deepseek-chat",
                config_json={
                    "provider_id": "db_deepseek",
                    "provider_type": "openai_compatible",
                    "model_name": "deepseek-chat",
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key_env": "DEEPSEEK_API_KEY",
                    "temperature": 0.8,
                    "max_tokens": 1024,
                    "timeout": 30,
                },
                enabled=True,
            )
        )
        session.merge(RoleModelBindingRecord(role_key="villager", provider_id="db_deepseek"))
        session.commit()

    client = TestClient(create_app())
    response = client.post(
        "/games",
        json={
            "board_id": "board_6_beginner",
            "human_player_id": "human",
            "human_role_key": "villager",
            "agent_ids": ["agent_linye", "agent_xiaoman", "agent_qingshan", "agent_akai", "agent_moyu"],
        },
    )

    assert response.status_code == 200
    human = next(player for player in response.json()["data"]["players"] if player["is_human"])
    yaml_bindings = load_llm_config_from_yaml().role_bindings
    expected_provider_id = next(
        binding.provider_id for binding in yaml_bindings if binding.role_key == "villager"
    )
    assert human["model_provider_id"] == expected_provider_id
