from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState


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
