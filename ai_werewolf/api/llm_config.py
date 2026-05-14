from fastapi import APIRouter, HTTPException, status

from ai_werewolf.api.games import configure_model_registry
from ai_werewolf.llm.model_config import LLMProviderConfig, RoleModelBinding, default_provider_configs, default_role_model_bindings
from ai_werewolf.llm.model_registry import ModelProviderRegistry, build_provider

router = APIRouter(prefix="/admin/llm", tags=["admin-llm"])

_providers: dict[str, LLMProviderConfig] = {provider.provider_id: provider for provider in default_provider_configs()}
_bindings: dict[str, RoleModelBinding] = {binding.role_key: binding for binding in default_role_model_bindings()}


def _sync_game_registry() -> None:
    registry = ModelProviderRegistry()
    for provider in _providers.values():
        registry.register(build_provider(provider))
    configure_model_registry(registry, list(_bindings.values()))


@router.post("/providers", status_code=status.HTTP_201_CREATED)
def create_provider(provider: LLMProviderConfig) -> LLMProviderConfig:
    _providers[provider.provider_id] = provider
    _sync_game_registry()
    return provider


@router.get("/providers")
def list_providers() -> list[LLMProviderConfig]:
    return list(_providers.values())


@router.post("/role-bindings", status_code=status.HTTP_201_CREATED)
def create_role_binding(binding: RoleModelBinding) -> RoleModelBinding:
    if binding.provider_id not in _providers:
        raise HTTPException(status_code=404, detail=f"unknown provider: {binding.provider_id}")
    _bindings[binding.role_key] = binding
    _sync_game_registry()
    return binding


@router.get("/role-bindings")
def list_role_bindings() -> list[RoleModelBinding]:
    return list(_bindings.values())
