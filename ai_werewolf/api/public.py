from fastapi import APIRouter

from ai_werewolf.api.responses import success_response
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards
from ai_werewolf.storage.catalog import list_enabled_agent_profiles, list_enabled_board_configs

router = APIRouter(tags=["public"])


@router.get("/boards")
def list_enabled_boards() -> dict:
    """获取所有启用的板子配置"""
    boards = list_enabled_board_configs()
    if boards is None:
        boards = [board for board in default_boards() if board.enabled]
    return success_response(data=boards)


@router.get("/agents")
def list_enabled_agents() -> dict:
    """获取所有启用的 AI 玩家"""
    agents = list_enabled_agent_profiles()
    if agents is None:
        agents = [agent for agent in default_agents() if agent.enabled]
    return success_response(data=agents)
