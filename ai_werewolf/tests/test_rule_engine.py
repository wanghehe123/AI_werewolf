"""Tests for RuleEngineProvider deterministic fallback."""

from __future__ import annotations

import pytest

from ai_werewolf.llm.chain.rule_engine import (
    RuleEngineProvider,
    _parse_prompt_context,
)


# ---------------------------------------------------------------------------
# Prompt templates for different roles / actions
# ---------------------------------------------------------------------------

WEREWOLF_KILL_PROMPT = (
    "玩家名称：wolf_ai\n"
    "你的真实身份：狼人\n"
    "当前阶段：night_action\n"
    "选择要击杀的玩家\n"
    "存活玩家：Alice(1号) wolf_ai(2号) Bob(3号)\n"
    "请做出你的决策。"
)

SEER_CHECK_PROMPT = (
    "玩家名称：seer_ai\n"
    "你的真实身份：预言家\n"
    "当前阶段：night_action\n"
    "选择要查验的玩家\n"
    "存活玩家：Alice(1号) seer_ai(2号) Bob(3号)\n"
    "请做出你的决策。"
)

WITCH_SAVE_PROMPT_N1 = (
    "玩家名称：witch_ai\n"
    "你的真实身份：女巫\n"
    "当前阶段：night_action\n"
    "第1夜\n"
    "是否使用解药\n"
    "存活玩家：Alice(1号) witch_ai(2号)\n"
    "请做出你的决策。"
)

WITCH_SAVE_PROMPT_N2 = (
    "玩家名称：witch_ai\n"
    "你的真实身份：女巫\n"
    "当前阶段：night_action\n"
    "第2夜\n"
    "是否使用解药\n"
    "存活玩家：Alice(1号) witch_ai(2号)\n"
    "请做出你的决策。"
)

WITCH_POISON_PROMPT = (
    "玩家名称：witch_ai\n"
    "你的真实身份：女巫\n"
    "当前阶段：night_action\n"
    "是否使用毒药\n"
    "存活玩家：Alice(1号) witch_ai(2号)\n"
    "请做出你的决策。"
)

VOTE_PROMPT = (
    "玩家名称：voter_ai\n"
    "你的真实身份：平民\n"
    "当前阶段：exile_vote\n"
    "投票放逐\n"
    "存活玩家：Alice(1号) voter_ai(2号) Bob(3号)\n"
    "请做出你的决策。"
)

SPEAK_PROMPT = (
    "玩家名称：speaker_ai\n"
    "你的真实身份：平民\n"
    "当前阶段：day_discussion\n"
    "发言\n"
    "存活玩家：Alice(1号) speaker_ai(2号) Bob(3号)\n"
    "请做出你的决策。"
)

HUNTER_SHOOT_PROMPT = (
    "玩家名称：hunter_ai\n"
    "你的真实身份：猎人\n"
    "当前阶段：night_action\n"
    "选择要带走的玩家\n"
    "存活玩家：Alice(1号) hunter_ai(2号) Bob(3号)\n"
    "请做出你的决策。"
)

EMPTY_PROMPT = ""


# ---------------------------------------------------------------------------
# Tests -- prompt parsing
# ---------------------------------------------------------------------------

class TestParsePromptContext:
    def test_werewolf_role(self) -> None:
        ctx = _parse_prompt_context(WEREWOLF_KILL_PROMPT)
        assert ctx["role_key"] == "werewolf"
        assert ctx["action_hint"] == "wolf_kill"

    def test_seer_role(self) -> None:
        ctx = _parse_prompt_context(SEER_CHECK_PROMPT)
        assert ctx["role_key"] == "seer"
        assert ctx["action_hint"] == "seer_check"

    def test_witch_role(self) -> None:
        ctx = _parse_prompt_context(WITCH_SAVE_PROMPT_N1)
        assert ctx["role_key"] == "witch"
        assert ctx["action_hint"] == "witch_save"
        assert ctx["night_number"] == 1

    def test_vote_action(self) -> None:
        ctx = _parse_prompt_context(VOTE_PROMPT)
        assert ctx["action_hint"] == "vote"

    def test_alive_players(self) -> None:
        ctx = _parse_prompt_context(WEREWOLF_KILL_PROMPT)
        assert len(ctx["alive_players"]) == 3
        ids = [p["player_id"] for p in ctx["alive_players"]]
        assert "Alice" in ids
        assert "wolf_ai" in ids

    def test_self_player_id(self) -> None:
        ctx = _parse_prompt_context(WEREWOLF_KILL_PROMPT)
        assert ctx["self_player_id"] == "wolf_ai"

    def test_empty_prompt(self) -> None:
        ctx = _parse_prompt_context(EMPTY_PROMPT)
        assert ctx["role_key"] is None
        assert ctx["alive_players"] == []

    def test_garbage_prompt(self) -> None:
        # Must never crash
        ctx = _parse_prompt_context("aslkdjflkajsdfklj234234@#$@#$")
        assert isinstance(ctx, dict)


# ---------------------------------------------------------------------------
# Tests -- RuleEngineProvider.decide
# ---------------------------------------------------------------------------

class TestRuleEngineProviderDecide:
    """Verify every role/action rule produces a valid PlayerDecision dict."""

    def _validate_schema(self, result: dict) -> None:
        """Check the result has all required PlayerDecision fields."""
        assert "speech" in result
        assert "action_type" in result
        assert "target_id" in result
        assert "public_reason" in result
        assert "private_memory_update" in result

    def test_werewolf_wolf_kill(self) -> None:
        engine = RuleEngineProvider()
        result = engine.decide(WEREWOLF_KILL_PROMPT)
        self._validate_schema(result)
        assert result["action_type"] == "wolf_kill"
        # Should target a non-self player
        assert result["target_id"] is not None
        assert result["target_id"] != "wolf_ai"

    def test_seer_seer_check(self) -> None:
        engine = RuleEngineProvider()
        result = engine.decide(SEER_CHECK_PROMPT)
        self._validate_schema(result)
        assert result["action_type"] == "seer_check"
        assert result["target_id"] is not None
        assert result["target_id"] != "seer_ai"

    def test_witch_save_night1(self) -> None:
        engine = RuleEngineProvider()
        result = engine.decide(WITCH_SAVE_PROMPT_N1)
        self._validate_schema(result)
        assert result["action_type"] == "witch_save"

    def test_witch_save_night2_no_action(self) -> None:
        engine = RuleEngineProvider()
        result = engine.decide(WITCH_SAVE_PROMPT_N2)
        self._validate_schema(result)
        assert result["action_type"] == "no_action"

    def test_witch_poison_never(self) -> None:
        engine = RuleEngineProvider()
        result = engine.decide(WITCH_POISON_PROMPT)
        self._validate_schema(result)
        assert result["action_type"] == "no_action"

    def test_vote(self) -> None:
        engine = RuleEngineProvider()
        result = engine.decide(VOTE_PROMPT)
        self._validate_schema(result)
        assert result["action_type"] == "vote"
        assert result["target_id"] is not None
        assert result["target_id"] != "voter_ai"

    def test_speak(self) -> None:
        engine = RuleEngineProvider()
        result = engine.decide(SPEAK_PROMPT)
        self._validate_schema(result)
        assert result["action_type"] == "speak"
        assert result["speech"]  # should be non-empty

    def test_hunter_shoot(self) -> None:
        engine = RuleEngineProvider()
        result = engine.decide(HUNTER_SHOOT_PROMPT)
        self._validate_schema(result)
        assert result["action_type"] == "hunter_shoot"
        assert result["target_id"] is not None
        assert result["target_id"] != "hunter_ai"

    def test_empty_prompt_default(self) -> None:
        engine = RuleEngineProvider()
        result = engine.decide(EMPTY_PROMPT)
        self._validate_schema(result)
        assert result["action_type"] == "no_action"

    def test_config_has_provider_id(self) -> None:
        engine = RuleEngineProvider()
        assert engine.config.provider_id == "rule_engine"


# ---------------------------------------------------------------------------
# Tests -- RuleEngineProvider.stream_speech
# ---------------------------------------------------------------------------

class TestRuleEngineProviderStreamSpeech:
    def test_yields_chunks(self) -> None:
        engine = RuleEngineProvider()
        chunks = list(engine.stream_speech(SPEAK_PROMPT))
        full = "".join(chunks)
        assert full  # non-empty
        assert full == engine.decide(SPEAK_PROMPT)["speech"]

    def test_empty_speech_no_chunks(self) -> None:
        engine = RuleEngineProvider()
        # Empty prompt -> default no_action with empty speech
        chunks = list(engine.stream_speech(EMPTY_PROMPT))
        assert chunks == []  # no speech to yield


# ---------------------------------------------------------------------------
# Tests -- model_registry integration
# ---------------------------------------------------------------------------

class TestBuildChainFromConfig:
    def test_builds_chain_with_rule_engine(self) -> None:
        from ai_werewolf.llm.model_registry import (
            ModelProviderRegistry,
            build_chain_from_config,
        )

        chain_config = [
            {"provider": "rule_engine", "timeout_ms": 50, "max_retries": 0},
        ]
        registry = ModelProviderRegistry()
        chain = build_chain_from_config(chain_config, registry)
        assert chain.total_budget_ms == 50

    @pytest.mark.asyncio
    async def test_chain_decides_with_rule_engine_only(self) -> None:
        from ai_werewolf.llm.model_registry import (
            ModelProviderRegistry,
            build_chain_from_config,
        )

        chain_config = [
            {"provider": "rule_engine", "timeout_ms": 50, "max_retries": 0},
        ]
        registry = ModelProviderRegistry()
        chain = build_chain_from_config(chain_config, registry)
        result = await chain.decide(SPEAK_PROMPT)
        assert result.tier_used == "rule_engine"
        assert result.response["action_type"] == "speak"


# ---------------------------------------------------------------------------
# Tests -- PlayerDecider with chain
# ---------------------------------------------------------------------------

class TestPlayerDeciderWithChain:
    def test_chain_path_produces_decision(self) -> None:
        from ai_werewolf.llm.chain.provider_chain import ProviderChain, ProviderTier
        from ai_werewolf.llm.chain.rule_engine import RuleEngineProvider
        from ai_werewolf.llm.player_decider import PlayerDecider
        from ai_werewolf.llm.providers import FakeModelProvider

        tiers = [
            ProviderTier(provider_id="rule_engine", model_name="rule", timeout_ms=50),
        ]
        chain = ProviderChain(tiers=tiers, providers={"rule_engine": RuleEngineProvider()})

        decider = PlayerDecider(model=FakeModelProvider(_config("fake")), chain=chain)
        decision = decider.decide(SPEAK_PROMPT)
        assert decision.action_type.value == "speak"
        assert decision.speech  # non-empty

    def test_no_chain_uses_single_provider(self) -> None:
        from ai_werewolf.llm.player_decider import PlayerDecider
        from ai_werewolf.llm.providers import FakeModelProvider

        decider = PlayerDecider(model=FakeModelProvider(_config("fake")))
        decision = decider.decide("any prompt")
        assert decision.action_type.value == "speak"


def _config(provider_id: str):
    from ai_werewolf.llm.model_config import LLMProviderConfig
    return LLMProviderConfig(
        provider_id=provider_id,
        provider_type="fake",
        model_name=f"test-{provider_id}",
    )
