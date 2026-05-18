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
from typing import Any, Protocol

from ai_werewolf.llm.model_config import LLMProviderConfig
from ai_werewolf.llm.prompts.template_loader import render_template

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
    OpenAI 兼容接口 Provider（使用 LangChain ChatOpenAI）

    支持所有兼容 OpenAI Chat Completions API 格式的服务，包括：
    - OpenAI (GPT-4o, GPT-4o-mini 等)
    - DeepSeek (deepseek-chat, deepseek-reasoner 等)
    - 通义千问 (qwen-plus, qwen-turbo 等)
    - SiliconFlow (GLM-4.7, Kimi-K2.5 等)
    - 本地 Ollama (qwen3, llama3 等)

    工作流程：
    1. 从配置中获取 base_url 和 API Key（通过环境变量）
    2. 使用 LangChain ChatOpenAI 发送请求（客户端可复用）
    3. System Prompt 指导模型返回 JSON 格式的决策
    4. 解析模型响应，提取 JSON 内容
    5. 如果解析失败，返回 fallback 决策
    """

    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config
        # Lazy-loaded LangChain client (cached in client_pool)
        self._llm_client: Any = None

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
        """Return the provider base URL without chat endpoint suffixes."""
        if not self.config.base_url:
            return None
        base_url = self.config.base_url.rstrip("/")
        # Remove /chat/completions suffix if present (common mistake)
        suffix = "/chat/completions"
        if base_url.lower().endswith(suffix):
            base_url = base_url[: -len(suffix)] or None
        return base_url

    def _sdk_base_url(self) -> str | None:
        """Return a transport-ready base URL for OpenAI-compatible SDK clients."""
        base_url = self._client_base_url()
        if base_url and not base_url.endswith("/v1"):
            return base_url + "/v1"
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
        return render_template("system/decision_system_prompt.st", {})

    def _build_speech_stream_system_prompt(self) -> str:
        return render_template("system/speech_stream_system_prompt.st", {})

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

    def _get_llm_client(self):
        """Get or create a cached LangChain or OpenAI-compatible client."""
        if self._llm_client is None:
            try:
                from ai_werewolf.llm.client_pool import get_chat_openai

                self._llm_client = get_chat_openai(
                    model=self.config.model_name,
                    api_key=self._get_api_key(),
                    base_url=self._client_base_url(),
                    timeout=self.config.timeout,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    max_retries=0,  # Disabled, ProviderChain handles fallback
                )
            except ModuleNotFoundError as exc:
                if exc.name != "langchain_openai":
                    raise
                logger.warning(
                    "Provider %s: langchain_openai 不可用，回退到 openai 兼容 SDK。model=%s base_url=%s",
                    self.config.provider_id,
                    self.config.model_name,
                    self._client_base_url() or "(未设置)",
                )
                from openai import OpenAI

                self._llm_client = OpenAI(
                    api_key=self._get_api_key(),
                    base_url=self._sdk_base_url(),
                    timeout=self.config.timeout,
                    max_retries=0,
                )
        return self._llm_client

    def _chat_completion(
        self,
        llm,
        prompt: str,
        max_tokens: int,
        *,
        timeout: int | None = None,
    ):
        """Call LangChain ChatOpenAI or OpenAI-compatible SDK."""
        if hasattr(llm, "invoke"):
            from ai_werewolf.llm.client_pool import get_chat_openai
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = get_chat_openai(
                model=self.config.model_name,
                api_key=self._get_api_key(),
                base_url=self._client_base_url(),
                timeout=timeout or self.config.timeout,
                max_tokens=max_tokens,
                temperature=self.config.temperature,
                max_retries=0,
            )
            messages = [
                SystemMessage(content=self._build_system_prompt()),
                HumanMessage(content=prompt),
            ]
            return llm.invoke(messages)

        return llm.chat.completions.create(
            model=self.config.model_name,
            messages=[
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=self.config.temperature,
            timeout=timeout or self.config.timeout,
        )

    def _response_content(self, response) -> str:
        """Extract content from LangChain or OpenAI-compatible responses."""
        if hasattr(response, "content"):
            return response.content
        choices = getattr(response, "choices", None)
        if choices:
            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", None)
            return content if isinstance(content, str) else str(content or "")
        return str(response)

    def _response_diagnostics(self, response) -> dict:
        """Extract diagnostic info from LangChain or OpenAI-compatible responses."""
        if hasattr(response, "response_metadata"):
            metadata = getattr(response, "response_metadata", {}) or {}
            usage = metadata.get("usage", {}) if metadata else {}
            return {
                "finish_reason": metadata.get("finish_reason", None),
                "content_chars": len(str(response.content)) if hasattr(response, "content") else 0,
                "reasoning_chars": 0,
                "usage": usage,
            }

        usage_obj = getattr(response, "usage", None)
        usage = usage_obj.model_dump() if hasattr(usage_obj, "model_dump") else {}
        finish_reason = None
        reasoning_chars = 0
        choices = getattr(response, "choices", None)
        if choices:
            finish_reason = getattr(choices[0], "finish_reason", None)
            message = getattr(choices[0], "message", None)
            reasoning_content = getattr(message, "reasoning_content", "") or ""
            reasoning_chars = len(reasoning_content)

        content = self._response_content(response)
        return {
            "finish_reason": finish_reason,
            "content_chars": len(content),
            "reasoning_chars": reasoning_chars,
            "usage": usage,
        }

    def _empty_content_retry_tokens(self, current_max_tokens: int, diagnostics: dict | None = None) -> int | None:
        # Detect reasoning model exhaustion: finish_reason=length + reasoning used all tokens
        if diagnostics and diagnostics.get("finish_reason") == "length":
            usage = diagnostics.get("usage", {})
            details = usage.get("completion_tokens_details") or {}
            reasoning_tokens = details.get("reasoning_tokens") or 0
            reasoning_chars = diagnostics.get("reasoning_chars", 0) or 0
            if (reasoning_tokens > 0 or reasoning_chars > 0) and diagnostics.get("content_chars", 1) == 0:
                if current_max_tokens >= 2048:
                    return None
                # Reasoning model exhausted budget on thinking — need much more headroom
                retry = max(current_max_tokens * 4, 8192)
                return retry if retry > current_max_tokens else None

        retry_max_tokens = min(max(current_max_tokens * 4, 2048), 8192)
        if retry_max_tokens <= current_max_tokens:
            return None
        return retry_max_tokens

    def _retry_timeout_seconds(self, retry_max_tokens: int) -> int:
        if retry_max_tokens <= self.config.max_tokens:
            return self.config.timeout
        return min(max(self.config.timeout + 5, int(self.config.timeout * 1.5)), 60)

    def decide(self, prompt: str) -> dict:
        """
        调用 LangChain ChatOpenAI 获取模型决策

        完整流程：
        1. 检查 API Key 是否已配置
        2. 获取或创建缓存的 LangChain ChatOpenAI 客户端（可复用连接）
        3. 发送 Chat Completion 请求（使用 SystemMessage + HumanMessage）
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
            # 获取或创建缓存的 LangChain ChatOpenAI 客户端
            llm = self._get_llm_client()
            request_stage = "initial_request"
            last_diagnostics: dict[str, Any] | None = None
            retry_max_tokens: int | None = None

            response = self._chat_completion(llm, prompt, self.config.max_tokens)

            # 提取响应文本
            content = self._response_content(response)
            if not content.strip():
                diagnostics = self._response_diagnostics(response)
                last_diagnostics = diagnostics
                retry_max_tokens = self._empty_content_retry_tokens(self.config.max_tokens, diagnostics)
                retried = False
                if retry_max_tokens is not None:
                    retried = True
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
                    request_stage = "retry_after_empty_content"
                    response = self._chat_completion(
                        llm,
                        prompt,
                        retry_max_tokens,
                        timeout=self._retry_timeout_seconds(retry_max_tokens),
                    )
                    content = self._response_content(response)
                if not content.strip():
                    diagnostics = self._response_diagnostics(response)
                    last_diagnostics = diagnostics
                    logger.warning(
                        "Provider %s: LLM %s返回空 content，将使用 fallback。model=%s base_url=%s "
                        "finish_reason=%s content_chars=%s reasoning_chars=%s usage=%s",
                        self.config.provider_id,
                        self.config.model_name,
                        "重试后仍" if retried else "在当前预算下",
                        base_url or "(未设置)",
                        diagnostics["finish_reason"],
                        diagnostics["content_chars"],
                        diagnostics["reasoning_chars"],
                        diagnostics["usage"],
                    )

            # 解析响应为结构化决策
            parsed = self._parse_response(content)

            # ---- 全链路诊断：标记 speech 为空的情况 ----
            speech_val = parsed.get("speech") if isinstance(parsed, dict) else None
            action_val = parsed.get("action_type") if isinstance(parsed, dict) else None
            if isinstance(speech_val, str) and not speech_val.strip() and action_val:
                # 夜晚私有行动（查验、刀人、用药、守人等）不需要公开发言，空speech是正常行为
                _NIGHT_ONLY_ACTIONS = {"seer_check", "wolf_kill", "witch_save", "witch_poison", "guard", "no_action", "hunter_shoot"}
                expected = action_val in _NIGHT_ONLY_ACTIONS
                log_func = logger.debug if expected else logger.info
                log_func(
                    "[PROVIDER_PARSE] provider=%s model=%s JSON解析成功但speech为空%s "
                    "action_type=%s target_id=%s raw_chars=%d raw_preview=%.200s",
                    self.config.provider_id,
                    self.config.model_name,
                    "（夜晚行动，预期行为）" if expected else "",
                    action_val,
                    parsed.get("target_id") if isinstance(parsed, dict) else "?",
                    len(content), content[:200],
                )
            return parsed

        except Exception:
            # 捕获所有异常（网络错误、API 错误、解析错误等）
            # 记录错误但不中断游戏，返回 fallback 决策
            logger.exception(
                "Provider %s: LLM API 调用失败，使用 fallback 响应。model=%s base_url=%s stage=%s retry_max_tokens=%s diagnostics=%s",
                self.config.provider_id,
                self.config.model_name,
                base_url or "(未设置)",
                locals().get("request_stage", "initial_request"),
                locals().get("retry_max_tokens"),
                locals().get("last_diagnostics"),
            )
            return self._fallback_decision(prompt, "LLM call failed")

    def stream_speech(self, prompt: str) -> Iterator[str]:
        """Stream plain public speech text using LangChain; fall back to chunked non-stream output."""
        api_key = self._get_api_key()
        base_url = self._client_base_url()
        if not api_key:
            yield from _chunk_text(self.decide(prompt)["speech"])
            return

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            # 获取或创建缓存的 LangChain ChatOpenAI 客户端
            llm = self._get_llm_client()

            # 使用 LangChain 的 stream() 方法
            messages = [
                SystemMessage(content=self._build_speech_stream_system_prompt()),
                HumanMessage(content=prompt),
            ]

            emitted = False
            for chunk in llm.stream(messages):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content:
                    emitted = True
                    yield content

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
