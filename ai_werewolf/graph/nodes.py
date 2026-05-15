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
) -> GameState:
    if len(agents) != board.player_count - 1:
        raise ValueError("agent count must fill board seats after human player")

    player_ids = [human_player_id] + [agent.agent_id for agent in agents]
    fixed_roles = {human_player_id: human_role_key} if human_role_key else None
    assigned = assign_roles(board, player_ids, seed=seed, fixed_roles=fixed_roles)
    players = [
        PlayerState(
            player_id=human_player_id,
            agent_id=None,
            seat=1,
            role_key=assigned[human_player_id],
            alive=True,
            is_human=True,
        )
    ]
    for index, agent in enumerate(agents, start=2):
        players.append(
            PlayerState(
                player_id=agent.agent_id,
                agent_id=agent.agent_id,
                seat=index,
                role_key=assigned[agent.agent_id],
                alive=True,
                is_human=False,
            )
        )

    return GameState(
        game_id="game_pending",
        board_id=board.board_id,
        phase=GamePhase.SETUP,
        day_count=0,
        players=players,
    )
