from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.boards import BoardConfig
from ai_werewolf.graph.builder import build_phase_plan
from ai_werewolf.graph.nodes import initialize_game_node
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.rules.win_conditions import evaluate_winner


class GameRunner:
    def __init__(self, role_registry: BuiltInRoleRegistry) -> None:
        self.role_registry = role_registry

    def phase_plan(self, board: BoardConfig) -> list[str]:
        return build_phase_plan(board, self.role_registry)

    def simulate_game(
        self,
        board: BoardConfig,
        human_player_id: str,
        agents: list[AgentProfile],
        seed: int | None = None,
    ):
        state = initialize_game_node(board, human_player_id, agents, seed=seed)
        for day in range(1, 11):
            state.day_count = day
            alive_wolf = next((player for player in state.players if player.alive and player.role_key == "werewolf"), None)
            if alive_wolf is not None:
                alive_wolf.alive = False
            winner = evaluate_winner(state, self.role_registry)
            if winner is not None:
                state.winner = winner.value
                return state
        state.winner = "villagers"
        return state
