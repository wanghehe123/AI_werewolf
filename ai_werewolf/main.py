"""
AI 狼人杀 FastAPI 应用入口
============================
创建和配置 FastAPI 应用实例。

启动时初始化：
1. 数据库持久化（如果配置了 DATABASE_URL）
2. LLM 模型注册中心（从 YAML 配置文件加载）
3. CORS 中间件（允许前端跨域访问）
4. 所有 API 路由
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ai_werewolf.api.admin import router as admin_router
from ai_werewolf.api.games import configure_game_repository, configure_model_registry, router as games_router
from ai_werewolf.api.llm_config import router as llm_config_router
from ai_werewolf.api.public import router as public_router
from ai_werewolf.api.responses import error_response, success_response
from ai_werewolf.llm.model_registry import build_registry_from_yaml
from ai_werewolf.storage.factory import build_game_repository, persistence_enabled

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用实例

    初始化流程：
    1. 创建 FastAPI 实例
    2. 配置数据库持久化（如果环境变量中设置了 DATABASE_URL）
    3. 从 YAML 配置文件加载 LLM Provider 并注册到游戏中
    4. 配置 CORS 中间件（允许前端开发服务器访问）
    5. 注册所有 API 路由
    6. 添加健康检查端点
    """
    app = FastAPI(title="AI Werewolf")

    # ---- 数据库持久化 ----
    if persistence_enabled():
        configure_game_repository(build_game_repository())

    # ---- LLM 模型初始化 ----
    # 从 YAML 配置文件加载 Provider 和角色绑定
    try:
        registry, role_bindings = build_registry_from_yaml()
        configure_model_registry(registry, role_bindings)
        logger.info("LLM 配置加载成功，已注册 %d 个 Provider", len(registry.all_provider_ids()))
    except Exception:
        logger.exception("LLM 配置加载失败，将使用默认配置")

    # ---- CORS 中间件 ----
    # 允许前端开发服务器（Vite 默认端口 5173）跨域访问后端 API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- 注册路由 ----
    app.include_router(public_router)       # 公开接口（板子列表、AI 列表）
    app.include_router(admin_router)        # 后台管理
    app.include_router(llm_config_router)   # LLM 配置管理
    app.include_router(games_router)        # 游戏核心接口

    # ---- 统一异常响应 ----
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(message=str(exc.detail), code=exc.status_code),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_response(message="validation error", code=422, data=exc.errors()),
        )

    # ---- 健康检查 ----
    @app.get("/health")
    def health() -> dict:
        return success_response(data={"status": "ok"})

    return app


# 创建全局应用实例（供 uvicorn 使用）
app = create_app()
