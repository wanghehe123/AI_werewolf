from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_werewolf.api.agents import router as agents_router
from ai_werewolf.api.boards import router as boards_router
from ai_werewolf.api.games import configure_game_repository, router as games_router
from ai_werewolf.api.llm_config import router as llm_config_router
from ai_werewolf.api.public import router as public_router
from ai_werewolf.storage.factory import build_game_repository, persistence_enabled


def create_app() -> FastAPI:
    app = FastAPI(title="AI Werewolf")
    if persistence_enabled():
        configure_game_repository(build_game_repository())
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(public_router)
    app.include_router(boards_router)
    app.include_router(agents_router)
    app.include_router(llm_config_router)
    app.include_router(games_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
