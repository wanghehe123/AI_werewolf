"""
LLM 配置管理 API
=================
提供 LLM Provider 和角色绑定的管理接口。

端点：
- POST /admin/llm/providers       创建新的 LLM Provider
- GET  /admin/llm/providers       列出所有 LLM Provider
- POST /admin/llm/role-bindings   创建角色-模型绑定
- GET  /admin/llm/role-bindings   列出所有角色-模型绑定

初始化时从 YAML 配置文件加载默认 Provider 和绑定。
"""

from fastapi import APIRouter, HTTPException, status

from ai_werewolf.api.responses import success_response
from ai_werewolf.api.games import configure_model_registry
from ai_werewolf.llm.model_config import (
    LLMProviderConfig,
    RoleModelBinding,
    load_llm_config_from_yaml,
)
from ai_werewolf.llm.model_registry import ModelProviderRegistry, build_provider

router = APIRouter(prefix="/admin/llm", tags=["admin-llm"])

# ---- 从 YAML 配置文件初始化 Provider 和绑定 ----
# 启动时加载 YAML 配置，作为管理 API 的初始状态
_initial_config = load_llm_config_from_yaml()
_providers: dict[str, LLMProviderConfig] = {
    provider.provider_id: provider for provider in _initial_config.providers
}
_bindings: dict[str, RoleModelBinding] = {
    binding.role_key: binding for binding in _initial_config.role_bindings
}


def _sync_game_registry() -> None:
    """将当前配置同步到游戏引擎的模型注册中心"""
    registry = ModelProviderRegistry()
    for provider in _providers.values():
        registry.register(build_provider(provider))
    configure_model_registry(registry, list(_bindings.values()))


@router.post("/providers", status_code=status.HTTP_201_CREATED)
def create_provider(provider: LLMProviderConfig) -> dict:
    """
    创建新的 LLM Provider

    添加一个新的 Provider 配置，并同步到游戏引擎。
    如果 provider_id 已存在，则更新配置。

    Args:
        provider: Provider 配置信息

    Returns:
        创建的 Provider 配置
    """
    _providers[provider.provider_id] = provider
    _sync_game_registry()
    return success_response(data=provider)


@router.get("/providers")
def list_providers() -> dict:
    """
    列出所有已配置的 LLM Provider

    Returns:
        Provider 配置列表
    """
    return success_response(data=list(_providers.values()))


@router.post("/role-bindings", status_code=status.HTTP_201_CREATED)
def create_role_binding(binding: RoleModelBinding) -> dict:
    """
    创建或更新角色-模型绑定

    将指定角色绑定到特定的 LLM Provider。
    如果角色已有绑定，则更新为新的 Provider。

    Args:
        binding: 角色-模型绑定信息

    Returns:
        创建的绑定信息

    Raises:
        404: 如果指定的 Provider 不存在
    """
    if binding.provider_id not in _providers:
        raise HTTPException(status_code=404, detail=f"unknown provider: {binding.provider_id}")
    _bindings[binding.role_key] = binding
    _sync_game_registry()
    return success_response(data=binding)


@router.get("/role-bindings")
def list_role_bindings() -> dict:
    """
    列出所有角色-模型绑定

    Returns:
        绑定列表
    """
    return success_response(data=list(_bindings.values()))
