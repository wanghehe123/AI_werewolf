from fastapi import APIRouter

from ai_werewolf.api.admin.auth import router as auth_router
from ai_werewolf.api.admin.players import router as players_router
from ai_werewolf.api.admin.agents import router as agents_router
from ai_werewolf.api.admin.boards import router as boards_router
from ai_werewolf.api.admin.roles import router as roles_router
from ai_werewolf.api.admin.games import router as games_router
from ai_werewolf.api.admin.health import router as health_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(players_router)
router.include_router(agents_router)
router.include_router(boards_router)
router.include_router(roles_router)
router.include_router(games_router)
router.include_router(health_router)
