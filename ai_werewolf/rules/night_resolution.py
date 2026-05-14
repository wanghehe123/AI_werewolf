from ai_werewolf.domain.actions import PlayerAction, PlayerActionType


def resolve_night_deaths(actions: list[PlayerAction]) -> list[str]:
    wolf_target: str | None = None
    saved_target: str | None = None
    poisoned_targets: set[str] = set()

    for action in actions:
        if action.action_type == PlayerActionType.WOLF_KILL:
            wolf_target = action.target_id
        elif action.action_type == PlayerActionType.WITCH_SAVE:
            saved_target = action.target_id
        elif action.action_type == PlayerActionType.WITCH_POISON and action.target_id is not None:
            poisoned_targets.add(action.target_id)

    deaths: set[str] = set(poisoned_targets)
    if wolf_target is not None and wolf_target != saved_target:
        deaths.add(wolf_target)

    return sorted(deaths)
