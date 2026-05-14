from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_werewolf.api.agents import router as agents_router
from ai_werewolf.api.boards import router as boards_router
from ai_werewolf.api.games import router as games_router
from ai_werewolf.api.public import router as public_router


def create_app() -> FastAPI:
    app = FastAPI(title="AI Werewolf")
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
    app.include_router(games_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
