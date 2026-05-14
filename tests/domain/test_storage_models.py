from ai_werewolf.storage.models import AgentProfileRecord, BoardRecord


def test_board_record_stores_json_config():
    record = BoardRecord(board_id="board_6", name="6人局", config_json={"player_count": 6}, enabled=True)

    assert record.board_id == "board_6"
    assert record.config_json["player_count"] == 6


def test_agent_record_stores_json_profile():
    record = AgentProfileRecord(agent_id="agent_1", name="林野", profile_json={"reasoning_level": 5}, enabled=True)

    assert record.profile_json["reasoning_level"] == 5
