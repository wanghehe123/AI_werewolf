from typing import Literal

from pydantic import BaseModel


class LLMProviderConfig(BaseModel):
    provider_id: str
    provider_type: Literal["fake", "openai_compatible"]
    model_name: str
    base_url: str | None = None
    api_key_env: str | None = None


class RoleModelBinding(BaseModel):
    role_key: str
    provider_id: str


def default_provider_configs() -> list[LLMProviderConfig]:
    return [
        LLMProviderConfig(provider_id="default", provider_type="fake", model_name="fake-default"),
        LLMProviderConfig(
            provider_id="openai_compatible_default",
            provider_type="openai_compatible",
            model_name="gpt-compatible",
            base_url="https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
        ),
    ]


def default_role_model_bindings() -> list[RoleModelBinding]:
    return [
        RoleModelBinding(role_key="werewolf", provider_id="default"),
        RoleModelBinding(role_key="seer", provider_id="default"),
        RoleModelBinding(role_key="witch", provider_id="default"),
        RoleModelBinding(role_key="hunter", provider_id="default"),
        RoleModelBinding(role_key="villager", provider_id="default"),
    ]
