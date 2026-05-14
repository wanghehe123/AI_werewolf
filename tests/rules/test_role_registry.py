from ai_werewolf.domain.roles import Faction
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


def test_builtin_registry_contains_core_roles():
    registry = BuiltInRoleRegistry()

    assert registry.get("werewolf").faction == Faction.WEREWOLF
    assert registry.get("seer").night_action == "seer_check"
    assert registry.get("witch").night_action == "witch_potion"
    assert registry.get("hunter").night_action is None
    assert registry.get("villager").faction == Faction.VILLAGER


def test_registry_reports_unknown_role():
    registry = BuiltInRoleRegistry()

    assert registry.has("white_wolf") is False
