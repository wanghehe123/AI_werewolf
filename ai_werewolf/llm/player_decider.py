"""
AI 玩家决策器
==============
封装 LLM 调用流程，为 AI 玩家提供决策能力。

核心职责：
1. 接收 prompt，调用 LLM 获取响应
2. 将 LLM 响应解析为结构化的 PlayerDecision
3. 对响应进行安全过滤
4. 处理 LLM 调用失败的情况（fallback 到安全响应）
"""

import logging
import json
import re
from collections.abc import Iterator
from typing import Protocol

from ai_werewolf.llm.safety import is_safe_speech
from ai_werewolf.llm.schemas import PlayerDecision

logger = logging.getLogger(__name__)


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

    def __init__(self, model: DecisionModel) -> None:
        """
        初始化决策器

        Args:
            model: 实现了 decide 方法的 LLM Provider
        """
        self.model = model

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
        # 调用 LLM 获取原始决策
        raw_decision = self.model.decide(prompt)

        try:
            # 使用 Pydantic 解析和校验决策结构
            decision = PlayerDecision.model_validate(raw_decision)
        except Exception:
            # 解析失败（字段缺失、类型错误等），回退到安全默认值
            logger.warning("LLM 决策解析失败，使用 fallback: %s", raw_decision)
            return PlayerDecision(
                speech=self._safe_fallback_speech(raw_decision),
                action_type="speak",
                target_id=None,
                public_reason=None,
                private_memory_update=None,
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
