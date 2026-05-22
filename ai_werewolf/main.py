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
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ai_werewolf.api.admin import router as admin_router
from ai_werewolf.api.evaluations import router as evaluations_router
from ai_werewolf.api.games import configure_game_repository, configure_model_registry, router as games_router
from ai_werewolf.api.socketio_bridge import sio
from ai_werewolf.api.llm_config import router as llm_config_router
from ai_werewolf.api.public import router as public_router
from ai_werewolf.api.responses import error_response, success_response
from ai_werewolf.config.env import load_local_env
from ai_werewolf.llm.model_config import LLMProviderConfig, RoleModelBinding, load_llm_config_from_yaml
from ai_werewolf.llm.model_registry import ModelProviderRegistry, build_provider, build_registry_from_yaml
from ai_werewolf.storage.database import configured_database_url, create_engine_and_tables
import socketio as socketio_lib

from ai_werewolf.storage.factory import build_game_repository, persistence_enabled
from ai_werewolf.storage.repositories import LLMConfigRepository


# ---------------------------------------------------------------------------
# Lifespan -- graceful shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context: close Redis clients on shutdown."""
    yield
    from ai_werewolf.infra.redis_client import close_clients
    await close_clients()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

LOCAL_DEV_CORS_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def _registry_from_database() -> tuple[ModelProviderRegistry, list[RoleModelBinding], list[LLMProviderConfig]] | None:
    engine = create_engine_and_tables(configured_database_url())
    with Session(engine) as session:
        repository = LLMConfigRepository(session)
        providers = repository.list_providers()
        if not providers:
            return None
        role_bindings = repository.list_role_bindings()

    registry = ModelProviderRegistry()
    for provider in providers:
        registry.register(build_provider(provider))
    default_provider_id = next(
        (provider.provider_id for provider in providers if provider.provider_id == "fake"),
        providers[0].provider_id,
    )
    registry.set_default(default_provider_id)
    return registry, role_bindings, providers


def _log_missing_llm_keys(providers: list[LLMProviderConfig], role_bindings: list[RoleModelBinding]) -> None:
    active_provider_ids = {binding.provider_id for binding in role_bindings}
    if not active_provider_ids:
        active_provider_ids = {providers[0].provider_id} if providers else set()

    providers_by_id = {provider.provider_id: provider for provider in providers}
    for provider_id in sorted(active_provider_ids):
        provider = providers_by_id.get(provider_id)
        if provider is None or provider.provider_type != "openai_compatible":
            continue
        # api_key 直接在 YAML 中配置时不需要环境变量
        if provider.api_key:
            continue
        if not provider.api_key_env or not os.getenv(provider.api_key_env):
            logger.warning(
                "LLM Provider %s 已被角色绑定使用，但 api_key 和 环境变量 %s 均未配置；调用时会进入 fallback",
                provider.provider_id,
                provider.api_key_env or "(未设置)",
            )


def _overlay_api_keys_from_yaml(providers: list[LLMProviderConfig]) -> None:
    """从 llm.yaml 覆写 api_key 到内存中的 Provider 配置。

    无论 Provider 从数据库还是 YAML 加载，api_key 永远以 llm.yaml 为准。
    """
    try:
        yaml_config = load_llm_config_from_yaml()
    except Exception:
        logger.warning("无法加载 YAML 配置文件用于覆写 api_key，将使用现有配置")
        return

    yaml_keys: dict[str, str] = {}
    for yaml_provider in yaml_config.providers:
        if yaml_provider.api_key:
            yaml_keys[yaml_provider.provider_id] = yaml_provider.api_key

    if not yaml_keys:
        return

    for provider in providers:
        yaml_key = yaml_keys.get(provider.provider_id)
        if yaml_key and yaml_key != provider.api_key:
            provider.api_key = yaml_key
            logger.info(
                "Provider %s: 已从 llm.yaml 覆写 api_key",
                provider.provider_id,
            )


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
    loaded_env_keys = load_local_env()
    if loaded_env_keys:
        logger.info("已从本地 env 文件加载环境变量: %s", ", ".join(loaded_env_keys))

    app = FastAPI(title="AI Werewolf", lifespan=lifespan)

    # ---- 数据库持久化 ----
    if persistence_enabled():
        configure_game_repository(build_game_repository())

    # ---- Redis 检查 ----
    from ai_werewolf.infra.redis_client import is_available as redis_is_available
    redis_ok = redis_is_available()
    if redis_ok:
        logger.info("Redis 连接成功")
    else:
        logger.warning("Redis 不可用，将使用内存模式（不支持多实例水平扩展）")

    # ---- LLM 模型初始化 ----
    # 始终从 YAML 加载配置（数据库配置已废弃）。
    try:
        llm_config = load_llm_config_from_yaml()
        registry, role_bindings = build_registry_from_yaml()
        chain_config = llm_config.chains.get("default")
        providers = [registry.get(provider_id).config for provider_id in registry.all_provider_ids() if registry.get(provider_id) is not None]
        logger.info("LLM 配置从 YAML 加载成功，已注册 %d 个 Provider", len(registry.all_provider_ids()))
        configure_model_registry(registry, role_bindings, chain_config=chain_config)
        _log_missing_llm_keys(providers, role_bindings)
    except Exception:
        logger.exception("LLM 配置加载失败，将使用默认配置")

    # ---- CORS 中间件 ----
    # 允许前端开发服务器（Vite 默认端口 5173，可能变更为 5174）跨域访问后端 API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
        ],
        allow_origin_regex=LOCAL_DEV_CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- 注册路由 ----
    app.include_router(public_router)       # 公开接口（板子列表、AI 列表）
    app.include_router(admin_router)        # 后台管理
    app.include_router(llm_config_router)   # LLM 配置管理
    app.include_router(games_router)        # 游戏核心接口
    app.include_router(evaluations_router)  # 自动评测接口

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


# 创建全局应用实例（供 uvicorn 使用），通过 Socket.IO ASGI 包装器提供双向实时通道
_fastapi_app = create_app()
app = socketio_lib.ASGIApp(sio, other_asgi_app=_fastapi_app)
