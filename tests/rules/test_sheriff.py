from ai_werewolf.domain.actions import PlayerAction, PlayerActionType
from ai_werewolf.rules.sheriff import resolve_sheriff_election


def test_sheriff_election_assigns_highest_vote_candidate():
    votes = [
        PlayerAction(actor_id="p1", action_type=PlayerActionType.VOTE, target_id="p3"),
        PlayerAction(actor_id="p2", action_type=PlayerActionType.VOTE, target_id="p3"),
        PlayerAction(actor_id="p3", action_type=PlayerActionType.VOTE, target_id="p2"),
    ]

    assert resolve_sheriff_election(votes) == "p3"


def test_sheriff_election_returns_none_on_tie():
    votes = [
        PlayerAction(actor_id="p1", action_type=PlayerActionType.VOTE, target_id="p2"),
        PlayerAction(actor_id="p2", action_type=PlayerActionType.VOTE, target_id="p1"),
    ]

    assert resolve_sheriff_election(votes) is None
