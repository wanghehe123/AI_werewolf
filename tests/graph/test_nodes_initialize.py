from ai_werewolf.graph.nodes import initialize_game_node
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards


def test_initialize_game_node_creates_players_with_roles():
    board = default_boards()[0]
    agents = default_agents()[:5]

    state = initialize_game_node(board=board, human_player_id="human", agents=agents, seed=1)

    assert len(state.players) == board.player_count
    assert any(player.is_human for player in state.players)
    assert len([player for player in state.players if player.role_key == "werewolf"]) == 2
