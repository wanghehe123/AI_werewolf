"""
LLM 模型配置模块
================
管理 LLM Provider 的配置信息，支持从 YAML 文件加载配置。

核心概念：
- LLMProviderConfig: 单个 LLM 服务的配置（API 地址、模型名、密钥等）
- RoleModelBinding:  游戏角色与 LLM Provider 的绑定关系
- LLMConfig:         完整的 LLM 配置（包含多个 Provider + 角色绑定）

配置加载优先级：
1. 环境变量 LLM_CONFIG_PATH 指定的 YAML 文件路径
2. 默认路径 ai_werewolf/config/llm.yaml
3. 如果 YAML 文件不存在，使用代码中的默认配置（fake provider）
"""

import os
from pathlib import Path
from typing import Any
from typing import Literal

import yaml
from pydantic import BaseModel


class LLMProviderConfig(BaseModel):
    """
    单个 LLM Provider 的配置

    Attributes:
        provider_id:   Provider 唯一标识，如 "deepseek", "local_ollama"
        provider_type: Provider 类型
            - "openai_compatible": OpenAI 兼容接口（OpenAI/DeepSeek/通义千问/Ollama 等）
            - "fake": 内置假模型，用于测试
        model_name:    模型名称，如 "deepseek-chat", "qwen3:8b"
        base_url:      API 基础地址，如 "https://api.deepseek.com/v1"
        api_key_env:   存放 API Key 的环境变量名，如 "DEEPSEEK_API_KEY"
                       运行时从 os.environ[api_key_env] 读取实际密钥
                       （如果直接在 YAML 中写了 api_key 则优先使用 api_key）
        api_key:       直接指定 API Key 值（个人开发使用，优先于 api_key_env）
                       生产环境建议使用 api_key_env 配合环境变量
        temperature:   生成温度 (0.0-2.0)，越高输出越随机
        max_tokens:    单次回复的最大 token 数
    timeout:       请求超时时间（秒）
        raise_on_error: ProviderChain 使用的内部开关。为 True 时 API 错误向上抛出，
                       由链路统一降级；普通单 provider 路径仍保持本地兜底。
    """

    provider_id: str
    provider_type: Literal["fake", "openai_compatible"]
    model_name: str
    base_url: str | None = None
    api_key_env: str | None = None
    api_key: str | None = None
    temperature: float = 0.8
    max_tokens: int = 1024
    timeout: int = 30
    raise_on_error: bool = False


class RoleModelBinding(BaseModel):
    """
    游戏角色与 LLM Provider 的绑定关系

    当 AI 玩家扮演某个角色时，会使用绑定的 Provider 进行决策和发言。
    例如：werewolf 角色绑定 deepseek provider，则所有狼人 AI 使用 DeepSeek 模型。

    Attributes:
        role_key:    游戏角色标识，如 "werewolf", "seer", "witch"
        provider_id: 对应的 LLM Provider ID
    """

    role_key: str
    provider_id: str


class LLMConfig(BaseModel):
    """
    完整的 LLM 配置

    包含多个 Provider 定义、角色绑定关系和默认 Provider。

    Attributes:
        providers:       所有可用的 LLM Provider 列表
        role_bindings:   角色与 Provider 的绑定列表
        default_provider: 当角色未在 role_bindings 中配置时使用的默认 Provider ID
    """

    providers: list[LLMProviderConfig]
    role_bindings: list[RoleModelBinding]
    default_provider: str = "fake"
    chains: dict[str, list[dict[str, Any]]] = {}


def default_provider_configs() -> list[LLMProviderConfig]:
    """
    返回默认的 Provider 配置列表（代码内硬编码的回退配置）

    当 YAML 配置文件不可用时使用此配置。包含：
    - fake: 假模型，用于测试
    - openai_compatible_default: OpenAI 兼容接口的占位配置

    Returns:
        Provider 配置列表
    """
    return [
        LLMProviderConfig(
            provider_id="default",
            provider_type="fake",
            model_name="fake-default",
        ),
        LLMProviderConfig(
            provider_id="openai_compatible_default",
            provider_type="openai_compatible",
            model_name="gpt-compatible",
            base_url="https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
        ),
    ]


def default_role_model_bindings() -> list[RoleModelBinding]:
    """
    返回默认的角色-模型绑定配置（所有角色都使用 fake provider）

    Returns:
        角色-模型绑定列表
    """
    return [
        RoleModelBinding(role_key="werewolf", provider_id="default"),
        RoleModelBinding(role_key="seer", provider_id="default"),
        RoleModelBinding(role_key="witch", provider_id="default"),
        RoleModelBinding(role_key="hunter", provider_id="default"),
        RoleModelBinding(role_key="villager", provider_id="default"),
    ]


def _default_yaml_path() -> Path:
    """
    获取默认的 YAML 配置文件路径

    Returns:
        指向 ai_werewolf/config/llm.yaml 的 Path 对象
    """
    return Path(__file__).parent.parent / "config" / "llm.yaml"


def load_llm_config_from_yaml(path: str | Path | None = None) -> LLMConfig:
    """
    从 YAML 文件加载 LLM 配置

    优先级：
    1. 参数 path 直接指定的路径
    2. 环境变量 LLM_CONFIG_PATH 指定的路径
    3. 默认路径 ai_werewolf/config/llm.yaml

    如果配置文件不存在或解析失败，回退到代码中的默认配置。

    Args:
        path: YAML 配置文件路径，为 None 时按优先级自动查找

    Returns:
        解析后的 LLMConfig 对象

    Raises:
        ValueError: YAML 文件存在但格式不正确时抛出
    """
    # 按优先级确定配置文件路径
    if path is not None:
        config_path = Path(path)
    elif os.getenv("LLM_CONFIG_PATH"):
        config_path = Path(os.getenv("LLM_CONFIG_PATH"))
    else:
        config_path = _default_yaml_path()

    # 如果配置文件不存在，回退到默认配置
    if not config_path.exists():
        return LLMConfig(
            providers=default_provider_configs(),
            role_bindings=default_role_model_bindings(),
            default_provider="default",
            chains={},
        )

    # 读取并解析 YAML 文件
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"LLM config file must be a YAML mapping, got {type(raw).__name__}")

    # 解析 providers 列表
    # YAML 中使用简写名 (id/type)，映射到模型字段 (provider_id/provider_type)
    providers = []
    for raw_provider in raw.get("providers", []):
        mapped = {
            "provider_id": raw_provider.get("id", raw_provider.get("provider_id")),
            "provider_type": raw_provider.get("type", raw_provider.get("provider_type")),
            "model_name": raw_provider.get("model_name", ""),
            "base_url": raw_provider.get("base_url"),
            "api_key_env": raw_provider.get("api_key_env"),
            "api_key": raw_provider.get("api_key"),
            "temperature": raw_provider.get("temperature", 0.8),
            "max_tokens": raw_provider.get("max_tokens", 1024),
            "timeout": raw_provider.get("timeout", 30),
        }
        providers.append(LLMProviderConfig(**mapped))

    # 解析 role_bindings（YAML 中是 dict，转为 RoleModelBinding 列表）
    raw_bindings = raw.get("role_bindings", {})
    role_bindings = [
        RoleModelBinding(role_key=role_key, provider_id=provider_id)
        for role_key, provider_id in raw_bindings.items()
    ]

    # 如果配置文件中没有任何 provider，回退到默认
    if not providers:
        providers = default_provider_configs()

    return LLMConfig(
        providers=providers,
        role_bindings=role_bindings,
        default_provider=raw.get("default_provider", "default"),
        chains=raw.get("chains", {}),
    )
