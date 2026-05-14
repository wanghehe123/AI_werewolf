from collections import Counter

from pydantic import BaseModel

from ai_werewolf.domain.actions import PlayerAction


class VoteResult(BaseModel):
    exiled_player_id: str | None
    tied_player_ids: list[str]


def resolve_single_vote(votes: list[PlayerAction]) -> VoteResult:
    counts = Counter(vote.target_id for vote in votes if vote.target_id is not None)
    if not counts:
        return VoteResult(exiled_player_id=None, tied_player_ids=[])

    top_count = max(counts.values())
    tied = sorted(player_id for player_id, count in counts.items() if count == top_count)
    if len(tied) > 1:
        return VoteResult(exiled_player_id=None, tied_player_ids=tied)
    return VoteResult(exiled_player_id=tied[0], tied_player_ids=[])
