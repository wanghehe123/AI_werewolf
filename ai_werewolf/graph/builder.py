from ai_werewolf.domain.boards import BoardConfig
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


def build_phase_plan(board: BoardConfig, role_registry: BuiltInRoleRegistry) -> list[str]:
    phases = ["initialize_game"]
    if board.sheriff_enabled:
        phases.append("sheriff_election")

    night_actions: dict[str, int] = {}
    for role_count in board.roles:
        role = role_registry.get(role_count.role_key)
        if role.night_action and role.phase_order is not None:
            night_actions[role.night_action] = role.phase_order

    phases.extend(action for action, _ in sorted(night_actions.items(), key=lambda item: item[1]))
    phases.extend([
        "resolve_night",
        "day_announcement",
        "speech_round",
        "vote_round",
        "resolve_vote",
        "check_win_condition",
    ])
    return phases
