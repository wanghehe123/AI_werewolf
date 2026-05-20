"""
模型 Provider 注册中心
=======================
管理所有可用的 LLM Provider，并为游戏角色分配对应的 Provider。

核心功能：
- 注册多个 Provider 实例
- 根据角色绑定关系，查找对应角色的 Provider
- 从 YAML 配置文件构建完整的注册中心
- 支持默认 Provider 回退机制
- 构建 ProviderChain 降级链
"""

import logging

from ai_werewolf.llm.chain.provider_chain import ProviderChain, ProviderTier
from ai_werewolf.llm.chain.rule_engine import RuleEngineProvider
from ai_werewolf.llm.model_config import (
    LLMConfig,
    LLMProviderConfig,
    RoleModelBinding,
    load_llm_config_from_yaml,
)
from ai_werewolf.llm.providers import (
    FakeModelProvider,
    ModelProvider,
    OpenAICompatibleProvider,
)

logger = logging.getLogger(__name__)


class ModelProviderRegistry:
    """
    模型 Provider 注册中心

    管理所有已注册的 LLM Provider，并根据角色绑定关系返回对应的 Provider。

    使用示例：
        registry = ModelProviderRegistry()
        registry.register(FakeModelProvider(config))
        provider = registry.provider_for_role("werewolf", bindings)
    """

    def __init__(self) -> None:
        # 内部存储：provider_id -> ModelProvider 实例
        self._providers: dict[str, ModelProvider] = {}
        # 默认 Provider ID，当角色未绑定或绑定的 Provider 不存在时使用
        self._default_provider_id: str = "default"

    def register(self, provider: ModelProvider) -> None:
        """
        注册一个 Provider 实例

        Args:
            provider: 实现 ModelProvider 协议的实例
        """
        self._providers[provider.config.provider_id] = provider

    def set_default(self, provider_id: str) -> None:
        """
        设置默认 Provider ID

        Args:
            provider_id: 默认 Provider 的唯一标识
        """
        self._default_provider_id = provider_id

    def provider_for_role(self, role_key: str, bindings: list[RoleModelBinding]) -> ModelProvider:
        """
        根据角色绑定关系，返回该角色对应的 Provider

        查找逻辑：
        1. 在 bindings 列表中查找 role_key 对应的 provider_id
        2. 如果找到，返回对应的 Provider 实例
        3. 如果 Provider 不存在（配置了但未注册），回退到默认 Provider
        4. 如果角色未在 bindings 中配置，也回退到默认 Provider

        Args:
            role_key: 游戏角色标识，如 "werewolf", "seer"
            bindings: 角色-模型绑定列表

        Returns:
            对应的 ModelProvider 实例

        Raises:
            KeyError: 如果绑定的 Provider 和默认 Provider 都不存在
        """
        # 查找角色绑定的 provider_id
        binding = next((b for b in bindings if b.role_key == role_key), None)
        provider_id = binding.provider_id if binding else self._default_provider_id

        # 尝试获取 Provider
        if provider_id in self._providers:
            return self._providers[provider_id]

        # 绑定的 Provider 不存在，回退到默认
        if provider_id != self._default_provider_id:
            logger.warning(
                "Provider %s (角色 %s 绑定) 不存在，回退到默认 Provider %s",
                provider_id,
                role_key,
                self._default_provider_id,
            )
            if self._default_provider_id in self._providers:
                return self._providers[self._default_provider_id]

        # 连默认 Provider 都没有
        raise KeyError(
            f"未找到 Provider: 角色绑定的 '{provider_id}' 和 "
            f"默认的 '{self._default_provider_id}' 均不存在"
        )

    def get(self, provider_id: str) -> ModelProvider | None:
        """
        按 ID 获取已注册的 Provider

        Args:
            provider_id: Provider 唯一标识

        Returns:
            ModelProvider 实例，不存在时返回 None
        """
        return self._providers.get(provider_id)

    def all_provider_ids(self) -> list[str]:
        """
        返回所有已注册的 Provider ID

        Returns:
            Provider ID 列表
        """
        return list(self._providers.keys())


def build_provider(config: LLMProviderConfig) -> ModelProvider:
    """
    根据 Provider 配置创建对应的 Provider 实例

    工厂函数，根据 provider_type 选择创建哪种 Provider：
    - "fake": 创建 FakeModelProvider（用于测试）
    - "openai_compatible": 创建 OpenAICompatibleProvider（真实 LLM API）

    Args:
        config: Provider 配置信息

    Returns:
        对应类型的 ModelProvider 实例

    Raises:
        ValueError: 不支持的 provider_type
    """
    if config.provider_type == "fake":
        return FakeModelProvider(config)
    if config.provider_type == "openai_compatible":
        return OpenAICompatibleProvider(config)
    raise ValueError(f"不支持的 Provider 类型: {config.provider_type}")


def build_registry_from_yaml(path: str | None = None) -> tuple[ModelProviderRegistry, list[RoleModelBinding]]:
    """
    从 YAML 配置文件构建完整的 Provider 注册中心

    完整流程：
    1. 加载 YAML 配置文件
    2. 为每个 Provider 创建实例并注册
    3. 设置默认 Provider
    4. 返回注册中心和角色绑定列表

    Args:
        path: YAML 文件路径，为 None 时使用默认路径

    Returns:
        (registry, role_bindings) 元组
        - registry: 已注册所有 Provider 的注册中心
        - role_bindings: 角色-模型绑定列表
    """
    # 加载配置
    config: LLMConfig = load_llm_config_from_yaml(path)

    # 构建注册中心
    registry = ModelProviderRegistry()
    for provider_config in config.providers:
        try:
            provider = build_provider(provider_config)
            registry.register(provider)
            logger.info("已注册 Provider: %s (类型: %s, 模型: %s)",
                        provider_config.provider_id,
                        provider_config.provider_type,
                        provider_config.model_name)
        except Exception:
            logger.exception("注册 Provider %s 失败，跳过", provider_config.provider_id)

    # 设置默认 Provider
    registry.set_default(config.default_provider)

    return registry, config.role_bindings


def build_chain_from_config(
    chain_config: list[dict],
    registry: ModelProviderRegistry,
    *,
    primary_provider_id: str | None = None,
) -> ProviderChain:
    """Build a :class:`ProviderChain` from a YAML ``chains`` section.

    For each tier in *chain_config* the provider is looked up in *registry*.
    If the provider id is ``"rule_engine"``, a :class:`RuleEngineProvider`
    is created automatically (it is never registered in the YAML providers
    section).

    Args:
        chain_config: List of tier dicts, each containing at least ``provider``
            and optional ``timeout_ms``, ``max_retries``, ``triggers_to_next``.
        registry: The registry that holds already-built providers.

    Returns:
        A fully wired :class:`ProviderChain`.
    """
    tiers: list[ProviderTier] = []
    providers: dict[str, ModelProvider] = {}
    entries = _normalize_chain_entries(chain_config, registry, primary_provider_id=primary_provider_id)

    for entry in entries:
        provider_id = entry.get("provider", entry.get("tier", "unknown"))
        configured_timeout_ms = entry.get("timeout_ms", 6000)
        max_retries = entry.get("max_retries", 1)
        triggers = list(entry.get("triggers_to_next", ["timeout", "5xx", "429", "json_parse_error"]))
        if provider_id != "rule_engine" and "provider_fallback" not in triggers:
            triggers.append("provider_fallback")
        effective_timeout_ms = configured_timeout_ms if provider_id == "rule_engine" else max(configured_timeout_ms, 1000)

        if provider_id == "rule_engine":
            providers[provider_id] = RuleEngineProvider()
        else:
            existing = registry.get(provider_id)
            if existing is not None:
                providers[provider_id] = _clone_provider_for_tier(existing, effective_timeout_ms)
            else:
                logger.warning(
                    "Chain tier '%s': provider not found in registry, "
                    "tier will be skipped at runtime.",
                    provider_id,
                )
        tier = ProviderTier(
            provider_id=provider_id,
            model_name=entry.get("model_name", provider_id),
            timeout_ms=effective_timeout_ms,
            max_retries=max_retries,
            triggers_to_next=list(triggers),
        )
        tiers.append(tier)

    return ProviderChain(tiers=tiers, providers=providers)


def build_decider_for_role(
    role_key: str,
    registry: ModelProviderRegistry,
    bindings: list[RoleModelBinding],
    *,
    chain_config: list[dict] | None = None,
):
    """Create a PlayerDecider for a role, optionally wiring the fallback chain."""
    from ai_werewolf.llm.player_decider import PlayerDecider

    provider = registry.provider_for_role(role_key, bindings)
    chain = None
    if chain_config:
        chain = build_chain_from_config(
            chain_config,
            registry,
            primary_provider_id=provider.config.provider_id,
        )
    return PlayerDecider(provider, chain=chain)


def _normalize_chain_entries(
    chain_config: list[dict],
    registry: ModelProviderRegistry,
    *,
    primary_provider_id: str | None = None,
) -> list[dict]:
    entries = [dict(entry) for entry in chain_config]
    if not entries or not primary_provider_id:
        return entries

    primary_entry = dict(entries[0])
    primary_entry["provider"] = primary_provider_id
    primary_provider = registry.get(primary_provider_id)
    if primary_provider is not None:
        primary_entry["model_name"] = primary_provider.config.model_name

    normalized = [primary_entry]
    seen_provider_ids = {primary_provider_id}
    for entry in entries:
        provider_id = entry.get("provider", entry.get("tier", "unknown"))
        if provider_id in seen_provider_ids:
            continue
        normalized.append(dict(entry))
        seen_provider_ids.add(provider_id)
    return normalized


def _clone_provider_for_tier(provider: ModelProvider, timeout_ms: int) -> ModelProvider:
    # Set the provider's SDK timeout to 70% of the chain tier timeout so that
    # the SDK raises properly-classified errors (429, 5xx, etc.) BEFORE the
    # chain's asyncio.wait_for cancels the call.  Without this gap,
    # asyncio.wait_for always wins the race and everything becomes a generic
    # TimeoutError, losing the real HTTP status code.
    provider_timeout_ms = int(timeout_ms * 0.7)
    timeout_seconds = max(2, provider_timeout_ms / 1000)
    cloned_config = provider.config.model_copy(update={"timeout": int(timeout_seconds), "raise_on_error": True})
    return build_provider(cloned_config)
