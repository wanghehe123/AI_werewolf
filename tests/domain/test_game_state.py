from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState


def test_game_state_tracks_players_and_phase():
    state = GameState(
        game_id="game_1",
        board_id="board_6_beginner",
        phase=GamePhase.SETUP,
        day_count=0,
        players=[
            PlayerState(player_id="p1", agent_id=None, seat=1, role_key="seer", alive=True, is_human=True),
            PlayerState(player_id="p2", agent_id="agent_linye", seat=2, role_key="werewolf", alive=True, is_human=False),
        ],
    )

    assert state.alive_player_ids() == ["p1", "p2"]
    assert state.player_by_id("p2").role_key == "werewolf"


def test_game_phase_matches_flow_design_without_sheriff_runtime_requirement():
    assert GamePhase.EXILE_VOTE.value == "exile_vote"
    assert GamePhase.LAST_WORDS.value == "last_words"
    assert GamePhase.SHERIFF_ELECTION.value == "sheriff_election"


def test_player_private_info_defaults_are_isolated():
    first = PlayerPrivateInfo()
    second = PlayerPrivateInfo()

    first.wolf_teammates.append("p2")
    first.seer_results.append({"round": "night1", "target": "p3", "result": "werewolf"})

    assert second.wolf_teammates == []
    assert second.seer_results == []
    assert first.witch_medicine == {"save": True, "poison": True}
