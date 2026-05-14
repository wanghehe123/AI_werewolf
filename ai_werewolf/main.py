from fastapi import FastAPI

from ai_werewolf.api.agents import router as agents_router
from ai_werewolf.api.boards import router as boards_router
from ai_werewolf.api.games import router as games_router


def create_app() -> FastAPI:
    app = FastAPI(title="AI Werewolf")
    app.include_router(boards_router)
    app.include_router(agents_router)
    app.include_router(games_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
