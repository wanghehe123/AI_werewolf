import random

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.boards import BoardConfig
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
from ai_werewolf.rules.assignment import assign_roles


def initialize_game_node(
    board: BoardConfig,
    human_player_id: str,
    agents: list[AgentProfile],
    seed: int | None = None,
    human_role_key: str | None = None,
    human_display_name: str | None = None,
) -> GameState:
    if len(agents) != board.player_count - 1:
        raise ValueError("agent count must fill board seats after human player")

    player_ids = [human_player_id] + [agent.agent_id for agent in agents]
    random.shuffle(player_ids)
    fixed_roles = {human_player_id: human_role_key} if human_role_key else None
    assigned = assign_roles(board, player_ids, seed=seed, fixed_roles=fixed_roles)
    players = [
        PlayerState(
            player_id=pid,
            agent_id=None if pid == human_player_id else pid,
            seat=index,
            role_key=assigned[pid],
            alive=True,
            is_human=pid == human_player_id,
            display_name=human_display_name if pid == human_player_id else None,
        )
        for index, pid in enumerate(player_ids, start=1)
    ]

    return GameState(
        game_id="game_pending",
        board_id=board.board_id,
        phase=GamePhase.SETUP,
        day_count=0,
        players=players,
    )


def initialize_ai_game_node(
    board: BoardConfig,
    players: list[tuple[str, AgentProfile]],
    seed: int | None = None,
) -> GameState:
    """Create an all-AI game state from database player ids and agent profiles."""
    if len(players) != board.player_count:
        raise ValueError("player count must match board seats")

    player_ids = [player_id for player_id, _agent in players]
    if len(set(player_ids)) != len(player_ids):
        raise ValueError("player ids must be unique")

    # Shuffle seat order so no player is always in a fixed seat
    combined = list(zip(player_ids, [a for _, a in players]))
    random.shuffle(combined)
    player_ids = [pid for pid, _ in combined]

    assigned = assign_roles(board, player_ids, seed=seed)
    return GameState(
        game_id="game_pending",
        board_id=board.board_id,
        phase=GamePhase.SETUP,
        day_count=0,
        players=[
            PlayerState(
                player_id=pid,
                agent_id=agent.agent_id,
                seat=index,
                role_key=assigned[pid],
                alive=True,
                is_human=False,
            )
            for index, (pid, agent) in enumerate(combined, start=1)
        ],
    )
