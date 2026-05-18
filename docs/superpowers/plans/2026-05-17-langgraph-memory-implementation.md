# LangGraph Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first production slice of the LangGraph decision-chain and memory-system design: clean baseline failures, introduce a Redis-backed memory store with a PostgreSQL stub, and route AI day speech through a structured decision-graph entry point.

**Architecture:** Keep the rollout narrow and reversible. First stabilize the current prompt/decider behavior, then add a memory abstraction behind a single interface, and finally layer a speech-focused decision graph on top of the existing scheduler/orchestrator flow with fallback to the current prompt path.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, LangGraph, pytest, Redis client

---

### Task 1: Stabilize current prompt and decider behavior

**Files:**
- Modify: `tests/llm/test_player_decider.py`
- Modify: `tests/llm/test_prompt_builder.py`
- Modify: `ai_werewolf/llm/player_decider.py`
- Modify: `ai_werewolf/llm/prompt_builder.py`

- [ ] **Step 1: Verify the current failures**

Run:

```bash
uv run pytest \
  tests/llm/test_player_decider.py \
  tests/llm/test_prompt_builder.py \
  -q
```

Expected:
- `test_decider_falls_back_for_empty_speech` fails
- `test_decider_falls_back_for_illegal_action_type` fails
- `test_speech_prompt_includes_board_context_and_seat_references_without_absent_roles` fails

- [ ] **Step 2: Keep the tests as the red baseline**

Do not loosen the expectations. Use the existing failing tests as the TDD red phase for:
- empty speech fallback
- illegal `action_type` fallback
- board-aware few-shot filtering

- [ ] **Step 3: Implement the minimal fixes**

Update `ai_werewolf/llm/player_decider.py` so that:
- invalid `action_type` always falls back to `speak`
- empty speech on fallback also resolves to a safe `speak` fallback
- add logs describing why fallback happened

Update `ai_werewolf/llm/prompt_builder.py` so that:
- few-shot examples are filtered by `enabled_role_keys`
- speech prompts for boards without `witch`/`hunter`/`guard` do not include those examples

- [ ] **Step 4: Re-run the focused tests**

Run:

```bash
uv run pytest \
  tests/llm/test_player_decider.py \
  tests/llm/test_prompt_builder.py \
  -q
```

Expected: all green

### Task 2: Introduce memory store contracts and tests

**Files:**
- Create: `tests/llm/test_memory_store.py`
- Create: `ai_werewolf/llm/memory/__init__.py`
- Create: `ai_werewolf/llm/memory/models.py`
- Create: `ai_werewolf/llm/memory/store.py`

- [ ] **Step 1: Write failing tests for store contracts**

Add tests covering:
- `RedisMemoryStore` key naming for global summary, player suspicion, private role memory, and decision trace
- `PostgresMemoryStore` behaving as a no-op stub
- envelope metadata including `schema_version`, `visibility`, and `payload_type`

- [ ] **Step 2: Run the new tests to confirm they fail**

Run:

```bash
uv run pytest tests/llm/test_memory_store.py -q
```

Expected: import or behavior failures because the memory modules do not exist yet

- [ ] **Step 3: Implement minimal memory models and store interface**

Add:
- `MemoryBackend`
- `RedisMemoryEnvelope`
- `DaySummary`
- `PlayerSuspicionMemory`
- `PrivateRoleMemory`
- `MemoryStore` protocol
- `RedisMemoryStore`
- `PostgresMemoryStore`

Keep `PostgresMemoryStore` as an explicit stub with logs and Chinese comments.

- [ ] **Step 4: Re-run the memory tests**

Run:

```bash
uv run pytest tests/llm/test_memory_store.py -q
```

Expected: all green

### Task 3: Add memory context builder

**Files:**
- Create: `tests/llm/test_memory_context_builder.py`
- Create: `ai_werewolf/llm/memory/context_builder.py`
- Modify: `ai_werewolf/engine/context.py`

- [ ] **Step 1: Write failing tests for memory context assembly**

Cover:
- recent public events window
- ordered day summaries
- player-specific suspicion memory selection
- player-specific private role memory selection
- no leakage across different `player_id`

- [ ] **Step 2: Run the new tests to confirm they fail**

Run:

```bash
uv run pytest tests/llm/test_memory_context_builder.py -q
```

Expected: failures because the builder does not exist yet

- [ ] **Step 3: Implement `MemoryContextBuilder`**

Add a small builder that:
- reads from `MemoryStore`
- uses `GameSession`
- returns a structured `MemoryContext`
- logs key assembly decisions in Chinese at `info`/`debug` level

- [ ] **Step 4: Re-run the context tests**

Run:

```bash
uv run pytest tests/llm/test_memory_context_builder.py ai_werewolf/tests/test_engine_context.py -q
```

Expected: all green

### Task 4: Add a speech-focused decision graph

**Files:**
- Create: `tests/llm/test_player_decision_graph.py`
- Create: `ai_werewolf/llm/graphs/player_decision_state.py`
- Create: `ai_werewolf/llm/graphs/player_decision_graph.py`
- Modify: `ai_werewolf/llm/action_scheduler.py`
- Modify: `ai_werewolf/engine/orchestrator.py`

- [ ] **Step 1: Write failing tests for the speech graph**

Cover:
- speech graph returns structured analysis, strategy, action draft, and final speech
- speech generation uses public facts plus player memory context
- graph falls back to legacy prompt path when a node errors

- [ ] **Step 2: Run the speech graph tests to confirm they fail**

Run:

```bash
uv run pytest tests/llm/test_player_decision_graph.py -q
```

Expected: failures because the graph is not implemented

- [ ] **Step 3: Implement the minimal speech graph**

Add nodes:
- `n1_analyze_situation`
- `n2_update_suspicion`
- `n3_decide_strategy`
- `n4_decide_action`
- `n5_generate_speech`
- `n6_validate_and_repair`

For the first slice:
- use lightweight deterministic transforms where possible
- keep `PlayerDecider` only in the speech generation or validation edge
- add Chinese comments before the complex state merge logic
- add logs around graph start, fallback, and final output

- [ ] **Step 4: Route AI day speech through the graph**

Update orchestration so day speech:
- builds `MemoryContext`
- invokes the speech graph
- falls back to the legacy speech prompt when needed

- [ ] **Step 5: Re-run the graph tests**

Run:

```bash
uv run pytest \
  tests/llm/test_player_decision_graph.py \
  tests/llm/test_action_scheduler.py \
  ai_werewolf/tests/test_engine_context.py \
  -q
```

Expected: all green

### Task 5: Verify the integrated slice

**Files:**
- Modify: `docs/superpowers/specs/2026-05-17-langgraph-memory-decision-design.md` only if implementation details materially changed

- [ ] **Step 1: Run the full focused suite**

Run:

```bash
uv run pytest \
  tests/llm/test_player_decider.py \
  tests/llm/test_prompt_builder.py \
  tests/llm/test_memory_store.py \
  tests/llm/test_memory_context_builder.py \
  tests/llm/test_player_decision_graph.py \
  tests/llm/test_action_scheduler.py \
  ai_werewolf/tests/test_engine_context.py \
  ai_werewolf/tests/test_werewolf_council.py \
  ai_werewolf/tests/test_witch_council.py \
  -q
```

Expected: all green

- [ ] **Step 2: Review logs and comments**

Check:
- key chain points have logs
- complex logic has short Chinese comments
- no debug spam in hot loops

- [ ] **Step 3: Commit the implementation slice**

Run:

```bash
git add \
  tests/llm/test_player_decider.py \
  tests/llm/test_prompt_builder.py \
  tests/llm/test_memory_store.py \
  tests/llm/test_memory_context_builder.py \
  tests/llm/test_player_decision_graph.py \
  ai_werewolf/llm/player_decider.py \
  ai_werewolf/llm/prompt_builder.py \
  ai_werewolf/llm/memory \
  ai_werewolf/llm/graphs/player_decision_state.py \
  ai_werewolf/llm/graphs/player_decision_graph.py \
  ai_werewolf/llm/action_scheduler.py \
  ai_werewolf/engine/context.py \
  ai_werewolf/engine/orchestrator.py
git commit -m "feat: add memory-backed speech decision graph"
```
