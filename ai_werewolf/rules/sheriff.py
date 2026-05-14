from ai_werewolf.domain.actions import PlayerAction
from ai_werewolf.rules.voting import resolve_single_vote


def resolve_sheriff_election(votes: list[PlayerAction]) -> str | None:
    return resolve_single_vote(votes).exiled_player_id
