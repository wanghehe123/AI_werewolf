from ai_werewolf.storage.catalog import board_to_domain_config
from ai_werewolf.storage.models import Board, BoardRole


def test_board_to_domain_config_infers_sheriff_rules_for_sheriff_enabled_board():
    board = Board(
        board_id="custom_board",
        name="自定义警长局",
        min_players=9,
        max_players=9,
        sheriff_enabled=True,
        enabled=True,
    )
    roles = [
        BoardRole(board_id="custom_board", role_key="werewolf", count=3),
        BoardRole(board_id="custom_board", role_key="seer", count=1),
        BoardRole(board_id="custom_board", role_key="villager", count=5),
    ]

    config = board_to_domain_config(board, roles)

    assert config.sheriff_enabled is True
    assert config.speech_rule.value == "sheriff_select_direction"
    assert config.vote_rule.value == "single_vote_with_pk"
