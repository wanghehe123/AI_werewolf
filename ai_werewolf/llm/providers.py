"""
LLM Provider 实现
==================
提供与 LLM 服务交互的 Provider 实现。

支持的 Provider 类型：
- FakeModelProvider:       假模型，用于测试和开发，不调用真实 API
- OpenAICompatibleProvider: OpenAI 兼容接口 Provider，支持所有兼容 OpenAI API 格式的服务
  包括：OpenAI、DeepSeek、通义千问、Ollama 等

所有 Provider 都实现 ModelProvider 协议（decide 方法），
返回一个 dict，可被 PlayerDecision 解析为结构化的玩家决策。
"""

import json
import logging
import os
import re
from collections.abc import Iterator
from typing import Protocol

from ai_werewolf.llm.model_config import LLMProviderConfig

logger = logging.getLogger(__name__)


class ModelProvider(Protocol):
    """
    模型 Provider 协议

    所有 LLM Provider 必须实现此协议，提供 decide 方法。
    decide 接收一个 prompt 字符串，返回一个可被 PlayerDecision 解析的 dict。

    Attributes:
        config: Provider 的配置信息
    """

    config: LLMProviderConfig

    def decide(self, prompt: str) -> dict:
        """
        让模型根据 prompt 做出决策

        Args:
            prompt: 输入给模型的提示词（包含角色信息、游戏状态等）

        Returns:
            包含决策信息的 dict，结构如下：
            {
                "speech": "发言内容",
                "action_type": "speak" | "vote" | "wolf_kill" | ...,
                "target_id": "目标玩家ID 或 None",
                "public_reason": "公开理由",
                "private_memory_update": "记忆更新 或 None"
            }
        """
        ...

    def stream_speech(self, prompt: str) -> Iterator[str]:
        """Yield speech text chunks for real-time display."""
        ...


def _chunk_text(text: str, size: int = 6) -> Iterator[str]:
    for index in range(0, len(text), size):
        yield text[index:index + size]


def _strip_thinking_blocks(text: str) -> str:
    """Remove reasoning blocks emitted by some compatible models."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE)
    return text.strip()


def _extract_first_target_id(prompt: str) -> str | None:
    matches = re.findall(r"([A-Za-z0-9_\-]+)（\d+号[^）]*）", prompt)
    return next((match for match in matches if match not in {"human", "null"}), None)


class FakeModelProvider:
    """
    假模型 Provider（用于测试和开发）

    不调用任何真实 API，返回固定的模拟决策。
    在没有配置 API Key 或进行测试时使用。
    """

    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config

    def decide(self, prompt: str) -> dict:
        """
        返回一个模拟的玩家决策

        Args:
            prompt: 输入提示词（本方法忽略其内容）

        Returns:
            固定的模拟决策 dict
        """
        return {
            "speech": "我会结合当前信息谨慎判断。",
            "action_type": "speak",
            "target_id": None,
            "public_reason": "fake model decision",
            "private_memory_update": None,
        }

    def stream_speech(self, prompt: str) -> Iterator[str]:
        """Return stable chunks for tests and local development."""
        yield from _chunk_text(self.decide(prompt)["speech"])


class OpenAICompatibleProvider:
    """
    OpenAI 兼容接口 Provider

    支持所有兼容 OpenAI Chat Completions API 格式的服务，包括：
    - OpenAI (GPT-4o, GPT-4o-mini 等)
    - DeepSeek (deepseek-chat, deepseek-reasoner 等)
    - 通义千问 (qwen-plus, qwen-turbo 等)
    - 本地 Ollama (qwen3, llama3 等)

    工作流程：
    1. 从配置中获取 base_url 和 API Key（通过环境变量）
    2. 使用 OpenAI SDK 发送 Chat Completion 请求
    3. System Prompt 指导模型返回 JSON 格式的决策
    4. 解析模型响应，提取 JSON 内容
    5. 如果解析失败，返回 fallback 决策
    """

    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config

    def _get_api_key(self) -> str | None:
        """
        读取 API Key，优先级：config.api_key > 环境变量(api_key_env)

        config.api_key 直接写在 YAML 配置中（个人开发用），
        api_key_env 则为环境变量名，从 os.environ 读取。

        Returns:
            API Key 字符串，如果两者均未配置则返回 None
        """
        if self.config.api_key:
            return self.config.api_key
        if not self.config.api_key_env:
            return None
        return os.getenv(self.config.api_key_env)

    def _client_base_url(self) -> str | None:
        """Return the OpenAI SDK base URL, accepting accidental full endpoint URLs."""
        if not self.config.base_url:
            return None
        base_url = self.config.base_url.rstrip("/")
        suffix = "/chat/completions"
        if base_url.lower().endswith(suffix):
            return base_url[: -len(suffix)] or None
        return base_url

    def _build_system_prompt(self) -> str:
        """
        构建 System Prompt，指导 LLM 返回结构化 JSON 决策

        System Prompt 的核心要求：
        - 像真实狼人杀玩家一样思考和发言
        - 返回严格的 JSON 格式
        - 不要暴露系统提示或隐藏信息
        - 发言要符合角色设定和游戏情境

        Returns:
            System Prompt 字符串
        """
        return (
            "你是一个狼人杀游戏的 AI 玩家。你需要根据当前的游戏状态做出决策。\n\n"
            "【重要规则】\n"
            "1. 你必须以纯 JSON 格式返回你的决策，不要包含任何其他文字、markdown 标记或代码块标记。\n"
            "2. JSON 格式如下：\n"
            '{\n'
            '  "speech": "你的发言内容（必须非空，用中文发言）",\n'
            '  "action_type": "<根据你的行动选择对应值>",\n'
            '  "target_id": "目标玩家ID（如果没有目标则填 null）",\n'
            '  "public_reason": "公开的理由（可以为 null）",\n'
            '  "private_memory_update": "你的内心想法（可以为 null）"\n'
            '}\n\n'
            "3. action_type 的有效取值：speak、vote、wolf_kill、seer_check、witch_save、witch_poison、guard、hunter_shoot、no_action\n"
            "4. 不要提及：系统提示、JSON、模型、LangGraph、隐藏字段、AI 等概念。\n"
            "5. 用中文发言，像一个真实的狼人杀玩家。\n"
            "6. 根据你的角色身份，做出合理的决策。\n"
            "7. 发言要自然、有逻辑，可以质疑别人、为自己辩护或表达观点。\n"
        )

    def _build_speech_stream_system_prompt(self) -> str:
        return (
            "你是一个狼人杀游戏的 AI 玩家。请根据用户提供的游戏状态直接输出你的公开发言正文。\n"
            "不要输出 JSON、Markdown、代码块、解释或系统信息。\n"
            "不要提及 prompt、模型、AI、隐藏字段。只用中文自然发言。"
        )

    def _parse_response(self, content: str) -> dict:
        """
        解析 LLM 返回的响应内容，提取 JSON 决策

        处理以下情况：
        1. 纯 JSON 字符串 -> 直接解析
        2. 包含在 ```json ... ``` 代码块中 -> 提取后解析
        3. 包含在 ``` ... ``` 代码块中 -> 提取后解析
        4. 文本中嵌入 JSON -> 尝试用括号匹配提取
        5. 所有解析均失败 -> 返回 fallback 决策

        Args:
            content: LLM 返回的原始文本内容

        Returns:
            解析后的决策 dict，如果解析失败返回 fallback
        """
        # 移除控制字符（除了 \n \r \t），避免 JSON 解析失败
        import unicodedata
        cleaned = _strip_thinking_blocks(content)
        cleaned = "".join(ch for ch in cleaned if unicodedata.category(ch)[0] != "C" or ch in "\n\r\t")
        cleaned = cleaned.strip()

        # 尝试 1: 直接解析整个响应为 JSON
        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        # 尝试 2: 提取 ```json ... ``` 代码块
        json_block_match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
        if json_block_match:
            try:
                result = json.loads(json_block_match.group(1).strip())
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        # 尝试 3: 用括号计数提取最外层 JSON 对象（支持任意嵌套层级）
        start = cleaned.find("{")
        if start != -1:
            depth = 0
            in_string = False
            escape = False
            for i in range(start, len(cleaned)):
                ch = cleaned[i]
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            result = json.loads(cleaned[start:i + 1])
                            if isinstance(result, dict):
                                return result
                        except json.JSONDecodeError:
                            pass
                        break

        # 所有解析尝试都失败，记录警告并返回 fallback
        logger.warning(
            "无法解析 LLM 响应为 JSON，使用 fallback 决策。响应内容: %s",
            content[:200],
        )
        return {
            "speech": _strip_thinking_blocks(content)[:100] if content else "我先保留意见。",
            "action_type": "speak",
            "target_id": None,
            "public_reason": None,
            "private_memory_update": None,
        }

    def _fallback_decision(self, prompt: str, reason: str) -> dict:
        """Return a varied local decision when the remote model is unavailable."""
        name_match = re.search(r"玩家名称：([^\n]+)", prompt)
        player_name = name_match.group(1).strip() if name_match else "我"
        target_id = _extract_first_target_id(prompt)
        if "当前阶段：night_action" in prompt:
            if "你的真实身份：狼人" in prompt:
                return {
                    "speech": "我选择今晚收益最高的刀口。",
                    "action_type": "wolf_kill",
                    "target_id": target_id,
                    "public_reason": reason,
                    "private_memory_update": None,
                }
            if "你的真实身份：预言家" in prompt:
                return {
                    "speech": "我查验一名发言和身份都需要确认的玩家。",
                    "action_type": "seer_check",
                    "target_id": target_id,
                    "public_reason": reason,
                    "private_memory_update": None,
                }
        if "当前阶段：exile_vote" in prompt:
            return {
                "speech": f"{player_name}会按当前发言压力投给最需要解释的位置。",
                "action_type": "vote",
                "target_id": target_id,
                "public_reason": reason,
                "private_memory_update": None,
            }
        role_match = re.search(r"你的真实身份：([^\n]+)", prompt)
        role_name = role_match.group(1).strip() if role_match else "好人"
        speech = (
            f"{player_name}先按{role_name}视角发言：我会重点看发言是否前后一致、投票是否跟逻辑匹配。"
            "目前先不急着定死身份，但会优先关注回避关键问题的位置。"
        )
        return {
            "speech": speech,
            "action_type": "speak",
            "target_id": None,
            "public_reason": reason,
            "private_memory_update": None,
        }

    def _chat_completion(self, client, prompt: str, max_tokens: int):
        return client.chat.completions.create(
            model=self.config.model_name,
            messages=[
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=self.config.temperature,
            max_tokens=max_tokens,
        )

    def _response_content(self, response) -> str:
        return response.choices[0].message.content or ""

    def _response_diagnostics(self, response) -> dict:
        choice = response.choices[0]
        message = choice.message
        reasoning_content = getattr(message, "reasoning_content", "") or ""
        usage = response.usage.model_dump() if getattr(response, "usage", None) else {}
        return {
            "finish_reason": getattr(choice, "finish_reason", None),
            "content_chars": len(getattr(message, "content", "") or ""),
            "reasoning_chars": len(reasoning_content),
            "usage": usage,
        }

    def _empty_content_retry_tokens(self, current_max_tokens: int) -> int | None:
        retry_max_tokens = min(max(current_max_tokens * 4, 2048), 4096)
        if retry_max_tokens <= current_max_tokens:
            return None
        return retry_max_tokens

    def decide(self, prompt: str) -> dict:
        """
        调用 OpenAI 兼容 API 获取模型决策

        完整流程：
        1. 检查 API Key 是否已配置
        2. 创建 OpenAI 客户端
        3. 发送 Chat Completion 请求
        4. 解析响应内容为结构化决策

        如果 API 调用失败（网络错误、Key 无效等），会记录错误并返回 fallback 决策，
        不会抛出异常，保证游戏流程不会因 LLM 故障而中断。

        Args:
            prompt: 包含角色信息、游戏状态等的提示词

        Returns:
            玩家决策 dict
        """
        api_key = self._get_api_key()
        base_url = self._client_base_url()

        # 如果没有 API Key，回退到假模型行为并记录警告
        if not api_key:
            logger.warning(
                "Provider %s: API Key 未配置（YAML api_key=%s，环境变量 %s），使用 fallback 响应。model=%s base_url=%s",
                self.config.provider_id,
                "已配置" if self.config.api_key else "未配置",
                self.config.api_key_env or "(未设置)",
                self.config.model_name,
                base_url or "(未设置)",
            )
            return self._fallback_decision(prompt, "API key not configured")

        try:
            # 延迟导入，避免在不需要时加载 openai 库
            from openai import OpenAI

            # 创建 OpenAI 客户端
            # base_url 支持自定义端点（DeepSeek、Ollama 等）
            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=self.config.timeout,
            )

            response = self._chat_completion(client, prompt, self.config.max_tokens)

            # 提取响应文本
            content = self._response_content(response)
            if not content.strip():
                diagnostics = self._response_diagnostics(response)
                retry_max_tokens = self._empty_content_retry_tokens(self.config.max_tokens)
                if retry_max_tokens is not None:
                    logger.warning(
                        "Provider %s: LLM 返回空 content，准备提高 max_tokens 后重试。model=%s base_url=%s "
                        "finish_reason=%s content_chars=%s reasoning_chars=%s usage=%s retry_max_tokens=%s",
                        self.config.provider_id,
                        self.config.model_name,
                        base_url or "(未设置)",
                        diagnostics["finish_reason"],
                        diagnostics["content_chars"],
                        diagnostics["reasoning_chars"],
                        diagnostics["usage"],
                        retry_max_tokens,
                    )
                    response = self._chat_completion(client, prompt, retry_max_tokens)
                    content = self._response_content(response)
                if not content.strip():
                    diagnostics = self._response_diagnostics(response)
                    logger.warning(
                        "Provider %s: LLM 重试后仍返回空 content，将使用 fallback。model=%s base_url=%s "
                        "finish_reason=%s content_chars=%s reasoning_chars=%s usage=%s",
                        self.config.provider_id,
                        self.config.model_name,
                        base_url or "(未设置)",
                        diagnostics["finish_reason"],
                        diagnostics["content_chars"],
                        diagnostics["reasoning_chars"],
                        diagnostics["usage"],
                    )

            # 解析响应为结构化决策
            return self._parse_response(content)

        except Exception:
            # 捕获所有异常（网络错误、API 错误、解析错误等）
            # 记录错误但不中断游戏，返回 fallback 决策
            logger.exception(
                "Provider %s: LLM API 调用失败，使用 fallback 响应。model=%s base_url=%s",
                self.config.provider_id,
                self.config.model_name,
                base_url or "(未设置)",
            )
            return self._fallback_decision(prompt, "LLM call failed")

    def stream_speech(self, prompt: str) -> Iterator[str]:
        """Stream plain public speech text; fall back to chunked non-stream output."""
        api_key = self._get_api_key()
        base_url = self._client_base_url()
        if not api_key:
            yield from _chunk_text(self.decide(prompt)["speech"])
            return

        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=self.config.timeout,
            )
            stream = client.chat.completions.create(
                model=self.config.model_name,
                messages=[
                    {"role": "system", "content": self._build_speech_stream_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                stream=True,
            )
            emitted = False
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    emitted = True
                    yield delta
            if not emitted:
                yield from _chunk_text(self.decide(prompt)["speech"])
        except Exception:
            logger.exception(
                "Provider %s: LLM 流式发言失败，使用 fallback 分片。model=%s base_url=%s",
                self.config.provider_id,
                self.config.model_name,
                base_url or "(未设置)",
            )
            yield from _chunk_text(self.decide(prompt)["speech"])
