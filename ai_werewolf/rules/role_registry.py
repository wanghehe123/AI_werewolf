from ai_werewolf.domain.roles import Faction, RoleDefinition


class BuiltInRoleRegistry:
    def __init__(self) -> None:
        self._roles = {
            "werewolf": RoleDefinition(
                key="werewolf",
                name="狼人",
                faction=Faction.WEREWOLF,
                night_action="wolf_kill",
                phase_order=10,
            ),
            "seer": RoleDefinition(
                key="seer",
                name="预言家",
                faction=Faction.VILLAGER,
                night_action="seer_check",
                phase_order=20,
            ),
            "witch": RoleDefinition(
                key="witch",
                name="女巫",
                faction=Faction.VILLAGER,
                night_action="witch_potion",
                phase_order=30,
            ),
            "hunter": RoleDefinition(
                key="hunter",
                name="猎人",
                faction=Faction.VILLAGER,
                night_action=None,
                phase_order=None,
            ),
            "villager": RoleDefinition(
                key="villager",
                name="平民",
                faction=Faction.VILLAGER,
                night_action=None,
                phase_order=None,
            ),
        }

    def get(self, role_key: str) -> RoleDefinition:
        return self._roles[role_key]

    def has(self, role_key: str) -> bool:
        return role_key in self._roles

    def all(self) -> list[RoleDefinition]:
        return list(self._roles.values())
