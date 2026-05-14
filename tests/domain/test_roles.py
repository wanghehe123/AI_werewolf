import pytest

from ai_werewolf.domain.roles import Faction, RoleDefinition


def test_role_definition_requires_unique_key_and_faction():
    role = RoleDefinition(
        key="seer",
        name="预言家",
        faction=Faction.VILLAGER,
        night_action="seer_check",
        phase_order=20,
        can_speak=True,
        can_vote=True,
    )

    assert role.key == "seer"
    assert role.faction == Faction.VILLAGER
    assert role.night_action == "seer_check"


def test_role_definition_rejects_empty_key():
    with pytest.raises(ValueError, match="role key cannot be empty"):
        RoleDefinition(
            key="",
            name="空角色",
            faction=Faction.VILLAGER,
            night_action=None,
            phase_order=None,
        )
