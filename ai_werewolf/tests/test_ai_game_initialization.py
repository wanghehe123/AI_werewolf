from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition
from ai_werewolf.graph.nodes import initialize_ai_game_node


def test_initialize_ai_game_node_uses_database_player_ids_for_all_ai_seats():
    board = BoardConfig(
        board_id="b1",
        name="三人评测板",
        roles=[
            BoardRoleCount(role_key="werewolf", count=1),
            BoardRoleCount(role_key="seer", count=1),
            BoardRoleCount(role_key="villager", count=1),
        ],
        sheriff_enabled=False,
        speech_rule=SpeechRule.SEAT_ORDER,
        vote_rule=VoteRule.SINGLE_VOTE,
        win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
    )
    players = [
        ("player-a", AgentProfile(agent_id="agent-a", name="A", persona="", speech_style="", reasoning_level=3, deception_level=3, aggression_level=3, cooperation_level=3, risk_preference="balanced", memory_style="focus_on_votes")),
        ("player-b", AgentProfile(agent_id="agent-b", name="B", persona="", speech_style="", reasoning_level=3, deception_level=3, aggression_level=3, cooperation_level=3, risk_preference="balanced", memory_style="focus_on_votes")),
        ("player-c", AgentProfile(agent_id="agent-c", name="C", persona="", speech_style="", reasoning_level=3, deception_level=3, aggression_level=3, cooperation_level=3, risk_preference="balanced", memory_style="focus_on_votes")),
    ]

    state = initialize_ai_game_node(board, players, seed=13)

    assert [player.player_id for player in state.players] == ["player-a", "player-b", "player-c"]
    assert [player.agent_id for player in state.players] == ["agent-a", "agent-b", "agent-c"]
    assert [player.seat for player in state.players] == [1, 2, 3]
    assert {player.is_human for player in state.players} == {False}
