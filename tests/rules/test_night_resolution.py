from ai_werewolf.domain.actions import PlayerAction, PlayerActionType
from ai_werewolf.rules.night_resolution import resolve_night_deaths


def test_wolf_kill_deaths_are_cancelled_by_witch_save():
    actions = [
        PlayerAction(actor_id="wolf_team", action_type=PlayerActionType.WOLF_KILL, target_id="p3"),
        PlayerAction(actor_id="p4", action_type=PlayerActionType.WITCH_SAVE, target_id="p3"),
    ]

    assert resolve_night_deaths(actions) == []


def test_witch_poison_adds_death():
    actions = [
        PlayerAction(actor_id="wolf_team", action_type=PlayerActionType.WOLF_KILL, target_id="p3"),
        PlayerAction(actor_id="p4", action_type=PlayerActionType.WITCH_POISON, target_id="p2"),
    ]

    assert resolve_night_deaths(actions) == ["p2", "p3"]
