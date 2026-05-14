from enum import StrEnum

from ai_werewolf.domain.game_state import GameState
from ai_werewolf.domain.roles import Faction
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


class Winner(StrEnum):
    WOLVES = "wolves"
    VILLAGERS = "villagers"


def evaluate_winner(state: GameState, role_registry: BuiltInRoleRegistry) -> Winner | None:
    alive_wolves = 0
    alive_non_wolves = 0
    for player in state.players:
        if not player.alive:
            continue
        role = role_registry.get(player.role_key)
        if role.faction == Faction.WEREWOLF:
            alive_wolves += 1
        else:
            alive_non_wolves += 1

    if alive_wolves == 0:
        return Winner.VILLAGERS
    if alive_wolves >= alive_non_wolves:
        return Winner.WOLVES
    return None
