# Player Decision LangChain Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the unified player decision graph so AI players extract better situation facts, update suspicion dynamically, and choose tactical strategies without moving legality checks out of deterministic rule nodes.

**Architecture:** Keep the existing 6-node LangGraph shape. Convert `n1_analyze_situation`, `n2_update_suspicion`, and `n3_decide_strategy` into optional LLM-backed semantic nodes with Pydantic validation and deterministic fallback. Keep `n4_decide_action` and `n6_validate_and_repair` rule-led, and narrow `n5_generate_decision` to language packaging only.

**Tech Stack:** Python, LangGraph, Pydantic, existing `PlayerDecider.decide_raw()`, existing provider fallback chain, pytest.

---

## Current Anchors

- Existing graph file: `ai_werewolf/llm/graphs/player_decision_graph.py`
- Existing graph state: `ai_werewolf/llm/graphs/player_decision_state.py`
- Existing decision schema: `ai_werewolf/llm/schemas.py`
- Existing memory models: `ai_werewolf/llm/memory/models.py`
- Existing memory context: `ai_werewolf/llm/memory/context_builder.py`
- Existing memory writeback: `ai_werewolf/llm/memory/summary_builder.py`
- Existing call sites:
  - `ai_werewolf/engine/orchestrator.py`
  - `ai_werewolf/engine/vote.py`
  - `ai_werewolf/engine/night.py`
- Existing tests:
  - `tests/llm/test_player_decision_graph.py`
  - `tests/llm/test_player_decider.py`
  - `tests/llm/test_memory_context_builder.py`
  - `tests/llm/test_memory_store.py`
  - `ai_werewolf/tests/test_engine_vote.py`
  - `ai_werewolf/tests/test_engine_night.py`

## Design Boundaries

- LLM nodes may infer semantics, contradictions, relationships, suspicion deltas, and tactical intent.
- LLM nodes must not directly execute game actions.
- `n4_decide_action` remains the first node that turns strategy into `action_type` and `target_id`.
- `n6_validate_and_repair` remains deterministic and always wins over LLM output.
- Each semantic node must have:
  - a Pydantic output schema,
  - a prompt builder,
  - a parser/validator,
  - a deterministic fallback,
  - unit tests for valid LLM output,
  - unit tests for malformed LLM output.

---

## Phase 0: Baseline Guardrails

### Task 0.1: Capture Baseline Test State

**Files:**
- Read: `docs/superpowers/specs/2026-05-18-ai-werewolf-system-status.md`
- No code changes.

- [ ] Run the focused graph tests:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

- [ ] Expected result: all tests in `tests/llm/test_player_decision_graph.py` pass.

- [ ] Run the existing vote/night integration tests that call the graph:

```bash
pytest ai_werewolf/tests/test_engine_vote.py ai_werewolf/tests/test_engine_night.py -q
```

- [ ] Expected result: existing vote/night tests pass before graph behavior changes.

### Task 0.2: Add a Small Fake Raw LLM Helper for Tests

**Files:**
- Modify: `tests/llm/test_player_decision_graph.py`

- [ ] Add a local fake class near the existing test helpers:

```python
class FakeRawDecider:
    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def decide_raw(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("FakeRawDecider has no response left")
        return self.responses.pop(0)
```

- [ ] Run the file to confirm the helper does not alter behavior:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

---

## Phase 1: Add Typed Semantic Schemas

### Task 1.1: Create Player Decision Semantic Models

**Files:**
- Create: `ai_werewolf/llm/graphs/player_decision_models.py`
- Test: `tests/llm/test_player_decision_graph.py`

- [ ] Add Pydantic models for `n1`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SituationContradiction(BaseModel):
    player_id: str
    type: str
    evidence: str


class RelationshipEdge(BaseModel):
    from_player_id: str = Field(alias="from")
    to_player_id: str = Field(alias="to")
    relation: Literal["support", "attack", "protect", "follow", "distance", "conflict", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)


class SituationAnalysis(BaseModel):
    key_facts: list[str] = Field(default_factory=list, max_length=8)
    contradictions: list[SituationContradiction] = Field(default_factory=list, max_length=8)
    relationship_edges: list[RelationshipEdge] = Field(default_factory=list, max_length=12)
    turning_points: list[str] = Field(default_factory=list, max_length=6)
    recent_messages: list[str] = Field(default_factory=list)
    low_signal_players: list[str] = Field(default_factory=list)
    checked_players: list[str] = Field(default_factory=list)
```

- [ ] Add Pydantic models for `n2`:

```python
class SuspicionRecordUpdate(BaseModel):
    target_player_id: str
    suspicion_score: float = Field(ge=0.0, le=1.0)
    delta: float = Field(ge=-1.0, le=1.0)
    reasons: list[str] = Field(default_factory=list, max_length=5)
    relationship_tags: list[str] = Field(default_factory=list, max_length=5)


class TrustedPlayer(BaseModel):
    player_id: str
    trust_score: float = Field(ge=0.0, le=1.0)
    reason: str


class SuspicionUpdate(BaseModel):
    suspicion_records: list[SuspicionRecordUpdate] = Field(default_factory=list, max_length=8)
    primary_target: str | None = None
    secondary_target: str | None = None
    trusted_players: list[TrustedPlayer] = Field(default_factory=list, max_length=5)

    def to_memory_records(self) -> list[dict]:
        return [
            {
                "target_player_id": record.target_player_id,
                "suspicion_score": record.suspicion_score,
                "delta": record.delta,
                "evidence": list(record.reasons),
                "relationship_tags": list(record.relationship_tags),
            }
            for record in self.suspicion_records
        ]
```

- [ ] Add Pydantic model for `n3`:

```python
class PlayerStrategy(BaseModel):
    strategy_type: Literal[
        "observe",
        "pressure_test",
        "vote_push",
        "attack",
        "defend",
        "bait",
        "distance",
        "night_probe",
        "night_eliminate",
    ]
    primary_target: str | None = None
    secondary_target: str | None = None
    goal: str
    tone: str
    risk: str | None = None
    speech_intent: str | None = None
    vote_intent: str | None = None
    supporting_fact: str | None = None
```

- [ ] Add validators that strip blank strings from list fields and cap overly long text fields to 160 Chinese characters.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

### Task 1.2: Extend Graph State Keys Without Changing Runtime Behavior

**Files:**
- Modify: `ai_werewolf/llm/graphs/player_decision_state.py`

- [ ] Add optional trace fields:

```python
semantic_node_errors: NotRequired[dict[str, str]]
semantic_node_sources: NotRequired[dict[str, str]]
```

- [ ] Keep existing keys unchanged so current call sites and tests remain compatible.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

---

## Phase 2: Extract Deterministic Fallbacks Before Adding LLM

### Task 2.1: Split Current n1/n2/n3 Logic Into Fallback Helpers

**Files:**
- Modify: `ai_werewolf/llm/graphs/player_decision_graph.py`

- [ ] Move the current body of `n1_analyze_situation()` into `_fallback_analyze_situation(state) -> dict[str, Any]`.

- [ ] Move the current body of `n2_update_suspicion()` into `_fallback_update_suspicion(state) -> dict[str, Any]`.

- [ ] Move the current body of `n3_decide_strategy()` into `_fallback_decide_strategy(state) -> dict[str, Any]`.

- [ ] Keep public node functions calling those helpers.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

### Task 2.2: Add Output Normalizers for Backward Compatibility

**Files:**
- Modify: `ai_werewolf/llm/graphs/player_decision_graph.py`
- Test: `tests/llm/test_player_decision_graph.py`

- [ ] Add `_normalize_analysis_for_state(analysis: SituationAnalysis) -> dict[str, Any]`.

- [ ] Ensure normalized analysis uses existing keys:
  - `key_facts`
  - `recent_messages`
  - `low_signal_players`
  - `checked_players`

- [ ] Also preserve new keys:
  - `contradictions`
  - `relationship_edges`
  - `turning_points`

- [ ] Add `_normalize_suspicion_for_state(update: SuspicionUpdate) -> dict[str, Any]`.

- [ ] Ensure normalized suspicion includes both:
  - `records` for existing `build_player_suspicion_memory()`
  - `suspicion_records` for richer graph consumers

- [ ] Add `_normalize_strategy_for_state(strategy: PlayerStrategy) -> dict[str, Any]`.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

---

## Phase 3: Add Prompt Builders for n1/n2/n3

### Task 3.1: Create Prompt Builder Module

**Files:**
- Create: `ai_werewolf/llm/graphs/player_decision_prompts.py`
- Test: `tests/llm/test_player_decision_graph.py`

- [ ] Add `build_situation_analysis_prompt(state: dict) -> str`.

- [ ] The prompt must include:
  - `game_id`
  - `player_id`
  - `role_key`
  - `decision_kind`
  - `alive_player_ids`
  - `memory_context.recent_events`
  - `memory_context.day_summaries`
  - `memory_context.private_role_memory`

- [ ] The prompt must request JSON only:

```json
{
  "key_facts": ["string"],
  "contradictions": [{"player_id": "string", "type": "string", "evidence": "string"}],
  "relationship_edges": [{"from": "string", "to": "string", "relation": "support", "confidence": 0.7}],
  "turning_points": ["string"]
}
```

- [ ] Add `build_suspicion_update_prompt(state: dict) -> str`.

- [ ] The prompt must include:
  - current role perspective,
  - `analysis`,
  - previous `suspicion_memory`,
  - recent vote/speech events available in `memory_context`,
  - instruction to output scores in `0.0` to `1.0`.

- [ ] Add `build_strategy_prompt(state: dict) -> str`.

- [ ] The prompt must include:
  - role key,
  - decision kind,
  - analysis,
  - suspicion update,
  - allowed strategy types,
  - instruction not to choose illegal action targets.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

### Task 3.2: Add Prompt Snapshot Assertions

**Files:**
- Modify: `tests/llm/test_player_decision_graph.py`

- [ ] Add a test that builds an n1 prompt and asserts it contains `"只输出 JSON"`.

- [ ] Add a test that builds an n2 prompt and asserts it contains `"0.0 到 1.0"`.

- [ ] Add a test that builds an n3 prompt and asserts it contains `"strategy_type"`.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

---

## Phase 4: Wire Optional LLM Semantic Nodes

### Task 4.1: Add Raw Semantic Decider Protocol

**Files:**
- Modify: `ai_werewolf/llm/graphs/player_decision_graph.py`

- [ ] Add a protocol near `DecisionGenerator`:

```python
class RawDecisionModel(Protocol):
    def decide_raw(self, prompt: str) -> dict:
        ...
```

- [ ] Import `Protocol` from `typing`.

- [ ] Do not change call sites yet.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

### Task 4.2: Make Graph Builder Accept Semantic Node Options

**Files:**
- Modify: `ai_werewolf/llm/graphs/player_decision_graph.py`

- [ ] Change `build_player_speech_graph()` signature:

```python
def build_player_speech_graph(
    decision_generator: DecisionGenerator | None = None,
    semantic_decider: RawDecisionModel | None = None,
    semantic_nodes: set[str] | None = None,
):
```

- [ ] Change `run_player_decision_graph()` signature:

```python
def run_player_decision_graph(
    *,
    agent: AgentProfile,
    player: PlayerState,
    memory_context: MemoryContext,
    decision_kind: str,
    decision_generator: DecisionGenerator | None = None,
    semantic_decider: RawDecisionModel | None = None,
    semantic_nodes: set[str] | None = None,
) -> dict[str, Any]:
```

- [ ] Default `semantic_nodes` to `set()` when absent.

- [ ] Pass the new arguments from `run_player_decision_graph()` to `build_player_speech_graph()`.

- [ ] Keep all existing callers valid because the new parameters are optional keyword-only parameters.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

### Task 4.3: Convert n1 Into an Optional LLM Node

**Files:**
- Modify: `ai_werewolf/llm/graphs/player_decision_graph.py`
- Test: `tests/llm/test_player_decision_graph.py`

- [ ] Add `_make_analyze_situation_node(semantic_decider, semantic_nodes)`.

- [ ] If `semantic_decider is None` or `"n1" not in semantic_nodes`, call `_fallback_analyze_situation(state)`.

- [ ] If enabled, build prompt with `build_situation_analysis_prompt(state)`.

- [ ] Call `semantic_decider.decide_raw(prompt)`.

- [ ] Validate with `SituationAnalysis.model_validate(raw)`.

- [ ] Merge fallback-only fields:
  - `recent_messages`
  - `low_signal_players`
  - `checked_players`

- [ ] On validation or LLM failure:
  - log warning with tag `[PLAYER_GRAPH_N1_LLM_FALLBACK]`,
  - return fallback analysis,
  - add `semantic_node_errors["n1"]`.

- [ ] Replace graph node registration:

```python
builder.add_node("n1_analyze_situation", _make_analyze_situation_node(semantic_decider, enabled_nodes))
```

- [ ] Add a test where fake n1 returns:

```python
{
    "key_facts": ["5号警上保1号，警下投1号，立场反复"],
    "contradictions": [{"player_id": "p5", "type": "speech_vote_conflict", "evidence": "保1号但投1号"}],
    "relationship_edges": [{"from": "p2", "to": "p5", "relation": "support", "confidence": 0.7}],
    "turning_points": ["5号改票后，1-5关系转为对立"]
}
```

- [ ] Assert result contains the LLM key fact and contradiction.

- [ ] Add a malformed-output test and assert fallback still returns `key_facts`.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

---

## Phase 5: Enable Phase 1 Rollout, n1 Only

### Task 5.1: Pass Semantic Decider From Day Speech Path

**Files:**
- Modify: `ai_werewolf/engine/orchestrator.py`

- [ ] In the AI speech path that calls `run_player_speech_graph()`, create the existing provider for `player.role_key`.

- [ ] Construct `PlayerDecider(provider)` once.

- [ ] Pass it as `semantic_decider=decider`.

- [ ] Pass `semantic_nodes={"n1"}`.

- [ ] Keep the existing `speech_generator` behavior unchanged.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py ai_werewolf/tests/test_engine_vote.py ai_werewolf/tests/test_engine_night.py -q
```

### Task 5.2: Pass Semantic Decider From Vote Path

**Files:**
- Modify: `ai_werewolf/engine/vote.py`

- [ ] Move provider/decider construction before `decision_generator`.

- [ ] Reuse that decider in `decision_generator`.

- [ ] Pass `semantic_decider=decider`.

- [ ] Pass `semantic_nodes={"n1"}`.

- [ ] Ensure `record_prompt_trace()` still records the n5 vote prompt.

- [ ] Run:

```bash
pytest ai_werewolf/tests/test_engine_vote.py tests/llm/test_player_decision_graph.py -q
```

### Task 5.3: Pass Semantic Decider From Night Path

**Files:**
- Modify: `ai_werewolf/engine/night.py`

- [ ] Move provider/decider construction before `decision_generator` in `_get_ai_decision()`.

- [ ] Reuse that decider for the final n5 night action decision.

- [ ] Pass `semantic_decider=decider`.

- [ ] Pass `semantic_nodes={"n1"}`.

- [ ] Ensure empty speech logging for private night actions still happens in `_get_ai_decision_with_prompt()`.

- [ ] Run:

```bash
pytest ai_werewolf/tests/test_engine_night.py tests/llm/test_player_decision_graph.py -q
```

---

## Phase 6: Upgrade n2 Suspicion Update

### Task 6.1: Add Rule Merge for Suspicion Updates

**Files:**
- Modify: `ai_werewolf/llm/graphs/player_decision_graph.py`
- Test: `tests/llm/test_player_decision_graph.py`

- [ ] Add `_merge_suspicion_with_rules(update, previous_records, alive_player_ids, self_player_id)`.

- [ ] Drop records whose `target_player_id` equals the acting player.

- [ ] Drop records whose `target_player_id` is not in `alive_player_ids`.

- [ ] Clamp `suspicion_score` and `delta` through Pydantic validation.

- [ ] Sort final records by descending `suspicion_score`.

- [ ] If `primary_target` is missing or illegal, use the top legal record.

- [ ] If no legal record exists, fallback to `_fallback_update_suspicion(state)`.

- [ ] Add tests for:
  - illegal self target dropped,
  - dead target dropped,
  - primary target repaired to top legal record.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

### Task 6.2: Convert n2 Into an Optional LLM Node

**Files:**
- Modify: `ai_werewolf/llm/graphs/player_decision_graph.py`
- Test: `tests/llm/test_player_decision_graph.py`

- [ ] Add `_make_update_suspicion_node(semantic_decider, semantic_nodes)`.

- [ ] If disabled, call `_fallback_update_suspicion(state)`.

- [ ] If enabled, build prompt with `build_suspicion_update_prompt(state)`.

- [ ] Validate raw output with `SuspicionUpdate.model_validate(raw)`.

- [ ] Normalize to state with `_normalize_suspicion_for_state()`.

- [ ] Rule-merge with `_merge_suspicion_with_rules()`.

- [ ] On failure:
  - log warning with tag `[PLAYER_GRAPH_N2_LLM_FALLBACK]`,
  - return fallback suspicion update,
  - add `semantic_node_errors["n2"]`.

- [ ] Add a test where fake n2 raises p5 from `0.57` to `0.82` and sets p2 as secondary.

- [ ] Assert `primary_target == "p5"` and `secondary_target == "p2"`.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

### Task 6.3: Enable n1+n2 in Call Sites

**Files:**
- Modify:
  - `ai_werewolf/engine/orchestrator.py`
  - `ai_werewolf/engine/vote.py`
  - `ai_werewolf/engine/night.py`

- [ ] Replace `semantic_nodes={"n1"}` with `semantic_nodes={"n1", "n2"}`.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py ai_werewolf/tests/test_engine_vote.py ai_werewolf/tests/test_engine_night.py -q
```

---

## Phase 7: Upgrade n3 Tactical Strategy

### Task 7.1: Convert n3 Into an Optional LLM Node

**Files:**
- Modify: `ai_werewolf/llm/graphs/player_decision_graph.py`
- Test: `tests/llm/test_player_decision_graph.py`

- [ ] Add `_make_decide_strategy_node(semantic_decider, semantic_nodes)`.

- [ ] If disabled, call `_fallback_decide_strategy(state)`.

- [ ] If enabled, build prompt with `build_strategy_prompt(state)`.

- [ ] Validate raw output with `PlayerStrategy.model_validate(raw)`.

- [ ] Normalize to state with `_normalize_strategy_for_state()`.

- [ ] If the strategy target is illegal, clear it and set `strategy_type="observe"` unless `suspicion_update.primary_target` is legal.

- [ ] On failure:
  - log warning with tag `[PLAYER_GRAPH_N3_LLM_FALLBACK]`,
  - return fallback strategy,
  - add `semantic_node_errors["n3"]`.

- [ ] Add a test where fake n3 returns:

```python
{
    "strategy_type": "pressure_test",
    "primary_target": "p5",
    "secondary_target": "p2",
    "goal": "轻踩5号观察2号是否继续补位保护",
    "tone": "冷静但带压迫感",
    "risk": "5如果是真预言家，强推会损失好人轮次",
    "speech_intent": "不直接归票，先要求5号解释投票矛盾",
    "vote_intent": "暂时倾向投5，但保留调整空间",
    "supporting_fact": "5号发言和投票不一致"
}
```

- [ ] Assert `strategy_type == "pressure_test"` and `action_draft.target_id == "p5"`.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

### Task 7.2: Enable n1+n2+n3 in Call Sites

**Files:**
- Modify:
  - `ai_werewolf/engine/orchestrator.py`
  - `ai_werewolf/engine/vote.py`
  - `ai_werewolf/engine/night.py`

- [ ] Replace `semantic_nodes={"n1", "n2"}` with `semantic_nodes={"n1", "n2", "n3"}`.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py ai_werewolf/tests/test_engine_vote.py ai_werewolf/tests/test_engine_night.py -q
```

---

## Phase 8: Narrow n5 Language Generation Responsibility

### Task 8.1: Lock Generated Decision Structure After n4

**Files:**
- Modify: `ai_werewolf/llm/graphs/player_decision_graph.py`
- Test: `tests/llm/test_player_decision_graph.py`

- [ ] Add `_language_only_decision(state, generated) -> PlayerDecision`.

- [ ] Always take these fields from `action_draft` or expected action:
  - `action_type`
  - `target_id`

- [ ] Accept from generated decision only:
  - `speech`
  - `public_reason` if present,
  - `private_memory_update` if present.

- [ ] Call `_language_only_decision()` inside `n6_validate_and_repair()` before final validation.

- [ ] Add a test where n5 returns `target_id="p2"` while n4 drafted `target_id="p5"`.

- [ ] Assert final decision target remains `"p5"`.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

### Task 8.2: Add Locked-Decision Prompt Suffix for Existing n5 Prompts

**Files:**
- Modify:
  - `ai_werewolf/engine/orchestrator.py`
  - `ai_werewolf/engine/vote.py`
  - `ai_werewolf/engine/night.py`

- [ ] Add a helper in each decision generator path or one shared local helper:

```python
def _append_locked_decision_block(prompt: str, state: dict[str, Any]) -> str:
    draft = state.get("action_draft", {})
    return (
        f"{prompt}\n\n"
        "【结构化决策已锁定】\n"
        f"- action_type: {draft.get('action_type')}\n"
        f"- target_id: {draft.get('target_id')}\n"
        "你只能生成自然发言和理由，不能改变 action_type 或 target_id。\n"
    )
```

- [ ] Use the helper before `decider.decide(task.prompt)`.

- [ ] Keep `record_prompt_trace()` recording the actual prompt sent to LLM.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py ai_werewolf/tests/test_engine_vote.py ai_werewolf/tests/test_engine_night.py -q
```

---

## Phase 9: Observability and Trace

### Task 9.1: Persist Semantic Node Source and Error Fields in Decision Result

**Files:**
- Modify: `ai_werewolf/llm/graphs/player_decision_graph.py`
- Test: `tests/llm/test_player_decision_graph.py`

- [ ] Ensure successful LLM node writes:

```python
semantic_node_sources = {"n1": "llm", "n2": "llm", "n3": "llm"}
```

- [ ] Ensure fallback node writes:

```python
semantic_node_sources = {"n1": "fallback"}
```

- [ ] Preserve existing result keys.

- [ ] Add assertions in fake LLM tests that sources are marked correctly.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

### Task 9.2: Add Prompt Trace Kinds for Semantic Nodes

**Files:**
- Modify:
  - `ai_werewolf/engine/orchestrator.py`
  - `ai_werewolf/engine/vote.py`
  - `ai_werewolf/engine/night.py`

- [ ] If the current `record_prompt_trace()` helper can be called from graph nodes without session access, use it.

- [ ] If session access is not available inside graph nodes, keep prompt trace for n5 only and log semantic node prompt summaries with logger tags:
  - `[PLAYER_GRAPH_N1_PROMPT]`
  - `[PLAYER_GRAPH_N2_PROMPT]`
  - `[PLAYER_GRAPH_N3_PROMPT]`

- [ ] Do not store full private role payloads in public logs.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py -q
```

---

## Phase 10: Full Verification

### Task 10.1: Run Focused LLM Graph Suite

**Files:**
- No code changes.

- [ ] Run:

```bash
pytest tests/llm/test_player_decision_graph.py tests/llm/test_player_decider.py tests/llm/test_memory_context_builder.py tests/llm/test_memory_store.py -q
```

- [ ] Expected result: all focused LLM/memory tests pass.

### Task 10.2: Run Vote and Night Regression Suite

**Files:**
- No code changes.

- [ ] Run:

```bash
pytest ai_werewolf/tests/test_engine_vote.py ai_werewolf/tests/test_engine_night.py -q
```

- [ ] Expected result: vote and night behavior remains legal and deterministic at action validation boundaries.

### Task 10.3: Run Full Test Suite

**Files:**
- No code changes.

- [ ] Run:

```bash
pytest -q
```

- [ ] Expected result: no regressions from the documented `382 passed` baseline.

---

## Rollout Order

1. Implement phases 0-5 and ship `n1` only.
2. Observe whether `analysis.key_facts`, `contradictions`, and `relationship_edges` are stable in traces.
3. Implement phase 6 and ship `n2`.
4. Observe whether suspicion memory stops behaving like a static ranking.
5. Implement phase 7 and ship `n3`.
6. Implement phase 8 before widening production use, so n5 cannot contradict n4.
7. Keep n4 and n6 deterministic throughout.

## Completion Criteria

- `n1` returns semantic key facts, contradictions, relationship edges, and turning points when LLM output is valid.
- `n2` returns dynamic suspicion records, primary target, secondary target, and trusted players when LLM output is valid.
- `n3` returns tactical strategy fields such as `pressure_test`, `goal`, `tone`, `risk`, `speech_intent`, and `vote_intent`.
- Malformed LLM output never breaks the graph.
- Illegal targets never survive `n4` and `n6`.
- n5 speech cannot change final `action_type` or `target_id`.
- Focused and full regression tests pass.
