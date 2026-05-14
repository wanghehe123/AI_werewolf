from ai_werewolf.domain.boards import BoardConfig
from ai_werewolf.domain.roles import Faction
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


class BoardValidationError(ValueError):
    pass


class BoardValidator:
    def __init__(self, role_registry: BuiltInRoleRegistry) -> None:
        self.role_registry = role_registry

    def validate(self, board: BoardConfig) -> None:
        werewolf_count = 0
        villager_count = 0

        for role_count in board.roles:
            if not self.role_registry.has(role_count.role_key):
                raise BoardValidationError(f"unknown role: {role_count.role_key}")
            role = self.role_registry.get(role_count.role_key)
            if role.faction == Faction.WEREWOLF:
                werewolf_count += role_count.count
            elif role.faction == Faction.VILLAGER:
                villager_count += role_count.count

        if werewolf_count < 1:
            raise BoardValidationError("board must contain at least one werewolf")
        if villager_count < 1:
            raise BoardValidationError("board must contain at least one villager faction player")
