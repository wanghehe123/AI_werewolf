import random
from collections import Counter

from ai_werewolf.domain.boards import BoardConfig


def assign_roles(
    board: BoardConfig,
    player_ids: list[str],
    seed: int | None = None,
    fixed_roles: dict[str, str] | None = None,
) -> dict[str, str]:
    if len(player_ids) != board.player_count:
        raise ValueError("player count does not match board")

    roles: list[str] = []
    for role_count in board.roles:
        roles.extend([role_count.role_key] * role_count.count)

    fixed_roles = fixed_roles or {}
    unknown_players = [player_id for player_id in fixed_roles if player_id not in player_ids]
    if unknown_players:
        raise ValueError(f"fixed role player is not in game: {unknown_players[0]}")

    available_counts = Counter(roles)
    requested_counts = Counter(fixed_roles.values())
    for role_key, count in requested_counts.items():
        if available_counts[role_key] < count:
            raise ValueError(f"fixed role {role_key} is not available in board")

    assigned = dict(fixed_roles)
    for role_key in fixed_roles.values():
        roles.remove(role_key)

    rng = random.Random(seed)
    rng.shuffle(roles)
    remaining_player_ids = [player_id for player_id in player_ids if player_id not in assigned]
    assigned.update(dict(zip(remaining_player_ids, roles, strict=True)))
    return assigned
