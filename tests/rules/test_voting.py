from ai_werewolf.domain.actions import PlayerAction, PlayerActionType
from ai_werewolf.rules.voting import VoteResult, resolve_single_vote


def test_resolve_single_vote_exiles_highest_vote_target():
    votes = [
        PlayerAction(actor_id="p1", action_type=PlayerActionType.VOTE, target_id="p3"),
        PlayerAction(actor_id="p2", action_type=PlayerActionType.VOTE, target_id="p3"),
        PlayerAction(actor_id="p3", action_type=PlayerActionType.VOTE, target_id="p2"),
    ]

    result = resolve_single_vote(votes)

    assert result == VoteResult(exiled_player_id="p3", tied_player_ids=[])


def test_resolve_single_vote_reports_tie():
    votes = [
        PlayerAction(actor_id="p1", action_type=PlayerActionType.VOTE, target_id="p2"),
        PlayerAction(actor_id="p2", action_type=PlayerActionType.VOTE, target_id="p1"),
    ]

    result = resolve_single_vote(votes)

    assert result.exiled_player_id is None
    assert result.tied_player_ids == ["p1", "p2"]
