import random

from ai_werewolf.domain.boards import BoardConfig


def assign_roles(board: BoardConfig, player_ids: list[str], seed: int | None = None) -> dict[str, str]:
    if len(player_ids) != board.player_count:
        raise ValueError("player count does not match board")

    roles: list[str] = []
    for role_count in board.roles:
        roles.extend([role_count.role_key] * role_count.count)

    rng = random.Random(seed)
    rng.shuffle(roles)
    return dict(zip(player_ids, roles, strict=True))
