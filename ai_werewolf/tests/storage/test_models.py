from ai_werewolf.storage.models import (
    AgentProfileRecord,
    Board,
    BoardRecord,
    BoardRole,
    GamePlayerRecord,
    GameRecord,
    LLMProviderRecord,
    Player,
    RoleMetadata,
    RoleModelBindingRecord,
)

def test_player_can_be_created():
    player = Player(name="测试玩家", is_ai=False)
    assert player.name == "测试玩家"
    assert player.is_ai == False
    assert player.player_id is not None

def test_role_metadata_fields():
    role = RoleMetadata(role_key="werewolf", name="狼人", faction="wolf", description="夜里杀人")
    assert role.role_key == "werewolf"
    assert role.faction == "wolf"

def test_board_has_roles():
    board = Board(name="测试板子", min_players=6, max_players=8)
    role = BoardRole(role_key="werewolf", count=2)
    board.roles.append(role)
    assert len(board.roles) == 1


def test_agent_profile_record_contains_admin_editable_fields():
    from ai_werewolf.storage.models import AgentProfileRecord

    agent = AgentProfileRecord(
        name="林野",
        persona="理性谨慎",
        speech_style="短句克制",
        avatar_prompt="冷静的年轻侦探",
        risk_preference="balanced",
        memory_style="focus_on_votes",
        default_model_provider_id="deepseek",
    )

    assert agent.agent_id
    assert agent.avatar_prompt == "冷静的年轻侦探"
    assert agent.default_model_provider_id == "deepseek"


def test_board_role_uses_board_and_role_as_identity():
    role = BoardRole(board_id="board_a", role_key="werewolf", count=2)

    assert role.board_id == "board_a"
    assert role.role_key == "werewolf"


def test_orm_table_names_match_database_schema_document():
    assert BoardRecord.__tablename__ == "board_records"
    assert LLMProviderRecord.__tablename__ == "llm_providers"
    assert RoleModelBindingRecord.__tablename__ == "role_model_bindings"
    assert GameRecord.__tablename__ == "games"
    assert GamePlayerRecord.__tablename__ == "game_players"
    assert Player.__tablename__ == "players"
    assert AgentProfileRecord.__tablename__ == "agent_profiles"
    assert Board.__tablename__ == "boards"
    assert BoardRole.__tablename__ == "board_roles"
    assert RoleMetadata.__tablename__ == "role_metadata"
