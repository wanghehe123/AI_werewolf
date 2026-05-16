import json
import logging

from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
from ai_werewolf.engine.context import build_private_infos
from ai_werewolf.engine.prompt_trace import record_prompt_trace
from ai_werewolf.engine.session import GameSession


def test_record_prompt_trace_writes_prompt_file_and_logs_metadata_only(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    player = PlayerState(player_id="ai_1", agent_id="ai_1", seat=2, role_key="werewolf", alive=True, is_human=False)
    state = GameState(game_id="g1", board_id="board", phase=GamePhase.EXILE_VOTE, day_count=1, players=[
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="seer", alive=True, is_human=True),
        player,
    ])
    session = GameSession(state=state, agents={}, human_player_id="human", private_infos=build_private_infos(state.players))
    prompt = "这是很长的投票 prompt，不应该直接塞进后台主日志。"
    caplog.set_level(logging.INFO, logger="ai_werewolf.engine.prompt_trace")

    path = record_prompt_trace(session, player.player_id, "exile_vote", prompt)

    assert path.read_text(encoding="utf-8") == prompt
    records = [record.message for record in caplog.records if record.message.startswith("prompt_trace ")]
    assert len(records) == 1
    payload = json.loads(records[0].removeprefix("prompt_trace "))
    assert payload["game_id"] == "g1"
    assert payload["prompt_kind"] == "exile_vote"
    assert payload["actor_id"] == "ai_1"
    assert payload["prompt_chars"] == len(prompt)
    assert payload["path"] == str(path)
    assert prompt not in records[0]
