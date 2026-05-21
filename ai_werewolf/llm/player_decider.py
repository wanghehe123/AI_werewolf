"""
AI 玩家决策器
==============
封装 LLM 调用流程，为 AI 玩家提供决策能力。

核心职责：
1. 接收 prompt，调用 LLM 获取响应
2. 将 LLM 响应解析为结构化的 PlayerDecision
3. 对响应进行安全过滤
4. 处理 LLM 调用失败的情况（fallback 到安全响应）
5. 支持 ProviderChain 降级链（可选）
"""

from __future__ import annotations

import asyncio
import logging
import json
import re
import threading
from collections.abc import AsyncIterator, Iterator
from typing import Any, TYPE_CHECKING, Protocol

from ai_werewolf.domain.actions import PlayerActionType
from ai_werewolf.llm.safety import is_safe_speech
from ai_werewolf.llm.schemas import PlayerDecision

if TYPE_CHECKING:
    from ai_werewolf.llm.chain.provider_chain import ProviderChain

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Persistent event loop for running async chain calls from sync context
# ------------------------------------------------------------------
# asyncio.run() creates a NEW event loop per call and CLOSES it at the end.
# This destroys httpx.AsyncClient connections created inside (e.g. by
# ChatOpenAI.ainvoke()) and causes "RuntimeError: Event loop is closed" on
# subsequent calls.  Instead we maintain ONE background thread with ONE
# persistent event loop that lives for the entire process lifetime.
# ------------------------------------------------------------------

_ASYNC_LOOP: asyncio.AbstractEventLoop | None = None
_ASYNC_LOOP_LOCK = threading.Lock()


def _persistent_loop() -> asyncio.AbstractEventLoop:
    """Return a loop that lives forever in a daemon thread."""
    global _ASYNC_LOOP
    with _ASYNC_LOOP_LOCK:
        if _ASYNC_LOOP is None or _ASYNC_LOOP.is_closed():
            _ASYNC_LOOP = asyncio.new_event_loop()
            t = threading.Thread(
                target=_ASYNC_LOOP.run_forever,
                daemon=True,
                name="player-decider-async-loop",
            )
            t.start()
        return _ASYNC_LOOP


def _sync_call_async(coro) -> Any:
    """Schedule *coro* on the persistent loop and block until done.

    Unlike ``asyncio.run()`` this does NOT close the loop, so httpx
    connections survive across calls.
    """
    loop = _persistent_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()  # raises the coroutine's exception if any


class DecisionModel(Protocol):
    """
    决策模型协议

    任何实现了 decide 方法的对象都可以作为 DecisionModel 使用，
    包括 FakeModelProvider 和 OpenAICompatibleProvider。
    """

    def decide(self, prompt: str) -> dict:
        ...

    def stream_speech(self, prompt: str) -> Iterator[str]:
        ...


class PlayerDecider:
    """
    AI 玩家决策器

    将 LLM 的原始响应转换为经过验证和安全过滤的 PlayerDecision 对象。
    如果 LLM 返回的内容不安全或无法解析，会回退到安全的默认响应。

    使用示例：
        decider = PlayerDecider(model_provider)
        decision = decider.decide("你正在扮演...")
        print(decision.speech)  # 安全的发言内容
    """

    def __init__(
        self,
        model: DecisionModel,
        chain: ProviderChain | None = None,
    ) -> None:
        """
        初始化决策器

        Args:
            model: 实现了 decide 方法的 LLM Provider
            chain: Optional degradation chain.  When provided, ``decide()``
                and ``stream_speech()`` will use the chain instead of the
                single *model*.  When *None* the existing single-provider
                behaviour is preserved (backward compatible).
        """
        self.model = model
        self._chain = chain
        self.last_chain_metadata: dict[str, Any] | None = None

    def decide(self, prompt: str) -> PlayerDecision:
        """
        让 AI 玩家根据 prompt 做出决策

        完整流程：
        1. 调用 LLM 获取原始响应（dict）
        2. 用 Pydantic 解析为 PlayerDecision（类型校验）
        3. 检查发言内容是否安全（不含系统术语等）
        4. 如果不安全，替换为默认安全发言

        Args:
            prompt: 包含角色信息和游戏状态的提示词

        Returns:
            经过验证和安全过滤的 PlayerDecision 对象
        """
        # If a chain is configured, delegate to the async chain path.
        if self._chain is not None:
            return self._decide_via_chain(prompt)

        self.last_chain_metadata = None
        # Original single-provider path (unchanged).
        raw_decision = self.model.decide(prompt)

        try:
            # 使用 Pydantic 解析和校验决策结构
            decision = PlayerDecision.model_validate(raw_decision)
        except Exception:
            # 解析失败（字段缺失、类型错误等），回退到安全默认值
            logger.warning("LLM 决策解析失败，使用 fallback: %s", raw_decision)
            return self._build_fallback(raw_decision)

        # 空发言处理：
        # - action_type="speak" 的空 speech 会被 Pydantic validator 拦截，不会到这里
        # - 其他 action（seer_check, wolf_kill, witch_save 等）是夜晚私有行动，不需要发言
        #   不能强制改为 speak（会丢失查验/刀人/救人目标），只替换 speech 占位即可
        if not decision.speech.strip():
            logger.info(
                "[DECIDER_EMPTY_SPEECH] 非发言行动，空speech正常 "
                "action_type=%s target_id=%s 保留原动作",
                decision.action_type, decision.target_id,
            )
            return PlayerDecision(
                speech=self._safe_fallback_speech(raw_decision),
                action_type=decision.action_type,
                target_id=decision.target_id,
                public_reason=decision.public_reason,
                private_memory_update=decision.private_memory_update,
            )

        # 安全校验：检查发言是否包含禁止术语
        if not is_safe_speech(decision.speech):
            logger.warning("不安全的发言被过滤: %s", decision.speech[:100])
            # 替换为安全发言，但保留其他决策信息
            return PlayerDecision(
                speech="我目前没有太多想说的，先听听大家的意见。",
                action_type=decision.action_type,
                target_id=decision.target_id,
                public_reason=decision.public_reason,
                private_memory_update=decision.private_memory_update,
            )

        return decision

    def decide_raw(self, prompt: str) -> dict:
        """Call the LLM and return the raw dict **without** PlayerDecision validation.

        This is intended for callers (like the LangGraph council graph) that
        ask for a custom JSON schema (e.g. ``{"target_id": "...", "reason":
        "...", "risk": 3}``) and handle parsing themselves.  Skipping
        validation avoids spurious "LLM 决策解析失败" warnings and preserves
        non-standard fields that ``PlayerDecision`` does not model.
        """
        if self._chain is not None:
            try:
                chain_result = _sync_call_async(self._chain.decide(prompt))
                return chain_result.response
            except Exception:
                logger.exception("ProviderChain failed in decide_raw, falling back to single provider")
                return self.model.decide(prompt)
        return self.model.decide(prompt)

    def stream_speech(self, prompt: str) -> Iterator[str]:
        """Yield safe speech chunks, falling back to normal decision if needed."""
        if not hasattr(self.model, "stream_speech"):
            yield self.decide(prompt).speech
            return

        raw_chunks: list[str] = []
        visible_chunks: list[str] = []
        try:
            source = _without_thinking_blocks(self.model.stream_speech(prompt), raw_chunks)
            yield from _public_speech_chunks(source, visible_chunks)
        except Exception:
            logger.exception("LLM 流式发言失败，回退到普通决策")
            yield self.decide(prompt).speech
            return

        speech = "".join(visible_chunks)
        if speech and not is_safe_speech(speech):
            logger.warning("不安全的流式发言被过滤: %s", speech[:100])

    # ------------------------------------------------------------------
    # Chain-based decision helpers
    # ------------------------------------------------------------------

    def _decide_via_chain(self, prompt: str) -> PlayerDecision:
        """Use the ProviderChain to get a decision, then validate and filter.

        与单 provider 路径（decide()）一致，包含空发言检查和安全性校验。
        """
        assert self._chain is not None  # guaranteed by caller
        self.last_chain_metadata = None
        try:
            chain_result = _sync_call_async(self._chain.decide(prompt))
        except Exception:
            logger.exception("ProviderChain failed, falling back to single provider")
            return self._build_fallback(self.model.decide(prompt))

        self.last_chain_metadata = _chain_metadata(chain_result)

        if chain_result.fallback_occurred:
            logger.info(
                "ProviderChain fell back to tier '%s'",
                chain_result.tier_used,
            )

        raw_decision = chain_result.response

        try:
            decision = PlayerDecision.model_validate(raw_decision)
        except Exception:
            logger.warning("Chain decision parse failed, using fallback: %s", raw_decision)
            return self._build_fallback(raw_decision)

        # 空发言检查 —— 与 decide() 保持一致：保留 action_type 和 target_id
        if not decision.speech.strip():
            logger.info(
                "[DECIDER_EMPTY_SPEECH] Chain路径，非发言行动空speech正常 "
                "action_type=%s target_id=%s 保留原动作",
                decision.action_type, decision.target_id,
            )
            return PlayerDecision(
                speech=self._safe_fallback_speech(raw_decision),
                action_type=decision.action_type,
                target_id=decision.target_id,
                public_reason=decision.public_reason,
                private_memory_update=decision.private_memory_update,
            )

        if not is_safe_speech(decision.speech):
            logger.warning("不安全的发言被过滤: %s", decision.speech[:100])
            return PlayerDecision(
                speech="我目前没有太多想说的，先听听大家的意见。",
                action_type=decision.action_type,
                target_id=decision.target_id,
                public_reason=decision.public_reason,
                private_memory_update=decision.private_memory_update,
            )

        return decision

    def _build_fallback(self, raw: dict) -> PlayerDecision:
        """Build fallback PlayerDecision, preserving action_type and target_id if possible.

        This is used when PlayerDecision.model_validate() fails (e.g. empty speech
        for non-speak actions, which is valid per our prompt examples).
        """
        if not isinstance(raw, dict):
            return PlayerDecision(
                speech="我先观察一下局势。",
                action_type="speak",
                target_id=None,
                public_reason=None,
                private_memory_update=None,
            )

        # Try to preserve the LLM's intent for action_type and target_id
        action_type = self._coerce_action_type(raw.get("action_type"))
        target_id = raw.get("target_id")
        # Normalize None → None (Pydantic handles None, but the dict may use it)
        if target_id is not None and not isinstance(target_id, str):
            target_id = None

        # Also try to preserve public_reason and private_memory_update
        public_reason = raw.get("public_reason") if isinstance(raw.get("public_reason"), str) else None
        private_memory_update = raw.get("private_memory_update") if isinstance(raw.get("private_memory_update"), str) else None

        return PlayerDecision(
            speech=self._safe_fallback_speech(raw),
            action_type=action_type,
            target_id=target_id,
            public_reason=public_reason,
            private_memory_update=private_memory_update,
        )

    def _build_default_speak_fallback(self, raw: dict) -> PlayerDecision:
        """统一构造 speak 兜底，避免非法动作继续流入后续链路。"""
        return PlayerDecision(
            speech=self._safe_fallback_speech(raw),
            action_type=PlayerActionType.SPEAK,
            target_id=None,
            public_reason=None,
            private_memory_update=None,
        )

    def _coerce_action_type(self, raw_action_type: object) -> PlayerActionType:
        """把模型返回的动作压缩到合法枚举，不合法时回退为 speak。"""
        if isinstance(raw_action_type, PlayerActionType):
            return raw_action_type
        if isinstance(raw_action_type, str):
            try:
                return PlayerActionType(raw_action_type)
            except ValueError:
                logger.warning("LLM 返回非法 action_type=%s，自动回退为 speak", raw_action_type)
        return PlayerActionType.SPEAK

    def _safe_fallback_speech(self, raw: dict) -> str:
        """
        从失败的 LLM 响应中提取安全发言

        如果原始响应中有 speech 字段且内容安全，则使用它；
        否则返回默认安全发言。

        Args:
            raw: LLM 返回的原始 dict

        Returns:
            安全的发言字符串
        """
        if not isinstance(raw, dict):
            return "我先观察一下局势。"
        speech = raw.get("speech", "")
        if isinstance(speech, str) and speech.strip() and is_safe_speech(speech):
            return speech[:200]  # 限制长度
        return "我先观察一下局势。"


def _strip_thinking_blocks(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE)
    return text


def _chain_metadata(chain_result: Any) -> dict[str, Any]:
    return {
        "tier_used": chain_result.tier_used,
        "fallback_occurred": chain_result.fallback_occurred,
        "attempts": chain_result.attempts,
    }


def _without_thinking_blocks(source: Iterator[str], raw_chunks: list[str]) -> Iterator[str]:
    """Yield stream chunks while dropping split <think>...</think> spans."""
    in_think = False
    pending = ""
    for chunk in source:
        raw_chunks.append(chunk)
        pending += chunk
        while pending:
            lowered = pending.lower()
            if in_think:
                end = lowered.find("</think>")
                if end == -1:
                    pending = ""
                    break
                pending = pending[end + len("</think>"):]
                in_think = False
                continue
            start = lowered.find("<think>")
            if start == -1:
                yield pending
                pending = ""
                break
            if start > 0:
                yield pending[:start]
            pending = pending[start + len("<think>"):]
            in_think = True


def _public_speech_chunks(source: Iterator[str], visible_chunks: list[str]) -> Iterator[str]:
    """Yield public speech, buffering JSON-shaped streams until speech is extracted."""
    buffered: list[str] = []
    decided_plain_text = False
    buffering_json = False

    for chunk in source:
        if decided_plain_text:
            visible_chunks.append(chunk)
            yield chunk
            continue

        buffered.append(chunk)
        candidate = "".join(buffered)
        stripped = candidate.lstrip()
        if not stripped:
            continue

        if stripped.startswith("{") or stripped.startswith("```"):
            buffering_json = True
            continue

        decided_plain_text = True
        visible_chunks.append(candidate)
        yield candidate

    if buffering_json:
        speech = _extract_speech_from_jsonish_stream("".join(buffered))
        if speech:
            visible_chunks.append(speech)
            yield speech


def _extract_speech_from_jsonish_stream(text: str) -> str:
    cleaned = _strip_thinking_blocks(text).strip()
    block_match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
    if block_match:
        cleaned = block_match.group(1).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return cleaned
        try:
            parsed = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return cleaned
    if isinstance(parsed, dict):
        speech = parsed.get("speech")
        if isinstance(speech, str):
            return speech
    return cleaned
