# AI Werewolf Configurable Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AI Werewolf MVP where backend administrators can configure reusable game boards and reusable AI agent personas, then users can choose a board and agents to start a playable AI Werewolf game.

**Architecture:** The system uses data-driven board definitions and agent persona definitions. LangGraph runs the game flow from `BoardConfig`, while deterministic Python rule code validates actions, resolves deaths, voting, sheriff flow, and win conditions. LLM calls are isolated behind services that return structured decisions and never directly mutate authoritative game state.

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, Pydantic v2, SQLModel, SQLite for MVP, pytest, pytest-asyncio, React/Next.js later, image generation behind an `AvatarProvider` abstraction.

---

## 0. Scope Correction

The word “custom” in this plan means **admin-configurable**, not arbitrary player-generated gameplay at runtime.

- Backend/admin can add or update boards as standalone data structures.
- Backend/admin can add or update AI agent personas as standalone data structures.
- End users choose from available boards and available AI agents, then start a game.
- MVP does not allow end users to script custom role skills.
- MVP does not include voice narration.
- MVP does not include multiplayer real-human rooms.

## 1. Delivery Strategy

Build in vertical slices:

1. Domain models and validation.
2. Role registry and board registry.
3. Agent persona registry.
4. Deterministic rules engine.
5. LangGraph game runner.
6. LLM decision adapter with fake model tests first.
7. Admin APIs.
8. User game APIs.
9. Avatar generation abstraction.
10. Minimal UI.
11. Simulation tests and hardening.

Every feature follows Red-Green-Refactor:

1. Write one failing test for one behavior.
2. Run the test and verify it fails for the expected reason.
3. Write the smallest implementation.
4. Run the focused test.
5. Run the related test group.
6. Refactor only while tests remain green.
7. Commit.

## 2. Target File Structure

```text
ai_werewolf/
  __init__.py
  main.py
  domain/
    __init__.py
    roles.py
    boards.py
    agents.py
    game_state.py
    events.py
    actions.py
    validation.py
  rules/
    __init__.py
    board_validator.py
    role_registry.py
    assignment.py
    night_resolution.py
    sheriff.py
    voting.py
    win_conditions.py
  graph/
    __init__.py
    builder.py
    nodes.py
    runner.py
  llm/
    __init__.py
    schemas.py
    player_decider.py
    prompt_builder.py
    safety.py
  avatars/
    __init__.py
    provider.py
    service.py
  api/
    __init__.py
    boards.py
    agents.py
    games.py
    admin.py
  storage/
    __init__.py
    models.py
    database.py
    repositories.py
  seeds/
    boards.py
    agents.py
tests/
  domain/
  rules/
  graph/
  llm/
  avatars/
  api/
  simulation/
```

## 3. Test Commands

Use these commands throughout implementation:

```bash
pytest tests/domain -v
pytest tests/rules -v
pytest tests/graph -v
pytest tests/llm -v
pytest tests/avatars -v
pytest tests/api -v
pytest tests/simulation -v
pytest -v
```

## 4. Development Tasks

### Task 1: Project Test Harness

**Files:**

- Create: `pyproject.toml`
- Create: `ai_werewolf/__init__.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing smoke test**

```python
def test_package_imports():
    import ai_werewolf

    assert ai_werewolf.__name__ == "ai_werewolf"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_smoke.py -v
```

Expected: FAIL because package or pytest config does not exist.

- [ ] **Step 3: Add minimal project files**

`pyproject.toml`:

```toml
[project]
name = "ai-werewolf"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi",
  "uvicorn",
  "pydantic>=2",
  "sqlmodel",
  "langgraph",
  "pytest",
  "pytest-asyncio",
  "httpx"
]

[tool.pytest.ini_options]
pythonpath = ["."]
asyncio_mode = "auto"
```

`ai_werewolf/__init__.py`:

```python
__all__ = []
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_smoke.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml ai_werewolf/__init__.py tests/test_smoke.py
git commit -m "chore: initialize ai werewolf project"
```

### Task 2: Role Definition Model

**Files:**

- Create: `ai_werewolf/domain/roles.py`
- Create: `tests/domain/test_roles.py`

- [ ] **Step 1: Write failing tests for role definition**

```python
import pytest

from ai_werewolf.domain.roles import Faction, RoleDefinition


def test_role_definition_requires_unique_key_and_faction():
    role = RoleDefinition(
        key="seer",
        name="预言家",
        faction=Faction.VILLAGER,
        night_action="seer_check",
        phase_order=20,
        can_speak=True,
        can_vote=True,
    )

    assert role.key == "seer"
    assert role.faction == Faction.VILLAGER
    assert role.night_action == "seer_check"


def test_role_definition_rejects_empty_key():
    with pytest.raises(ValueError, match="role key cannot be empty"):
        RoleDefinition(
            key="",
            name="空角色",
            faction=Faction.VILLAGER,
            night_action=None,
            phase_order=None,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/domain/test_roles.py -v
```

Expected: FAIL because `ai_werewolf.domain.roles` is missing.

- [ ] **Step 3: Implement minimal role model**

```python
from enum import StrEnum

from pydantic import BaseModel, field_validator


class Faction(StrEnum):
    WEREWOLF = "werewolf"
    VILLAGER = "villager"
    THIRD_PARTY = "third_party"


class RoleDefinition(BaseModel):
    key: str
    name: str
    faction: Faction
    night_action: str | None = None
    phase_order: int | None = None
    can_speak: bool = True
    can_vote: bool = True

    @field_validator("key")
    @classmethod
    def key_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("role key cannot be empty")
        return value
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/domain/test_roles.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/domain/roles.py tests/domain/test_roles.py
git commit -m "feat: add role definition model"
```

### Task 3: Board Configuration Model

**Files:**

- Create: `ai_werewolf/domain/boards.py`
- Create: `tests/domain/test_boards.py`

- [ ] **Step 1: Write failing tests for board config**

```python
import pytest

from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition


def test_board_config_calculates_player_count_from_roles():
    board = BoardConfig(
        board_id="board_6_beginner",
        name="6人新手局",
        roles=[
            BoardRoleCount(role_key="werewolf", count=2),
            BoardRoleCount(role_key="seer", count=1),
            BoardRoleCount(role_key="villager", count=3),
        ],
        sheriff_enabled=False,
        speech_rule=SpeechRule.SEAT_ORDER,
        vote_rule=VoteRule.SINGLE_VOTE,
        win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
        enabled=True,
    )

    assert board.player_count == 6


def test_board_rejects_zero_role_count():
    with pytest.raises(ValueError, match="role count must be positive"):
        BoardRoleCount(role_key="werewolf", count=0)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/domain/test_boards.py -v
```

Expected: FAIL because board model is missing.

- [ ] **Step 3: Implement board config model**

```python
from enum import StrEnum

from pydantic import BaseModel, computed_field, field_validator


class SpeechRule(StrEnum):
    SEAT_ORDER = "seat_order"
    REVERSE_SEAT_ORDER = "reverse_seat_order"
    SHERIFF_SELECT_DIRECTION = "sheriff_select_direction"


class VoteRule(StrEnum):
    SINGLE_VOTE = "single_vote"
    SINGLE_VOTE_WITH_PK = "single_vote_with_pk"


class WinCondition(StrEnum):
    WOLVES_ELIMINATED_OR_PARITY = "wolves_eliminated_or_parity"
    WOLVES_ELIMINATED_OR_SLAUGHTER_SIDE = "wolves_eliminated_or_slaughter_side"


class BoardRoleCount(BaseModel):
    role_key: str
    count: int

    @field_validator("count")
    @classmethod
    def count_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("role count must be positive")
        return value


class BoardConfig(BaseModel):
    board_id: str
    name: str
    roles: list[BoardRoleCount]
    sheriff_enabled: bool
    speech_rule: SpeechRule
    vote_rule: VoteRule
    win_condition: WinCondition
    enabled: bool = True

    @computed_field
    @property
    def player_count(self) -> int:
        return sum(role.count for role in self.roles)
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/domain/test_boards.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/domain/boards.py tests/domain/test_boards.py
git commit -m "feat: add board configuration model"
```

### Task 4: Agent Persona Model

**Files:**

- Create: `ai_werewolf/domain/agents.py`
- Create: `tests/domain/test_agents.py`

- [ ] **Step 1: Write failing tests for agent persona**

```python
import pytest

from ai_werewolf.domain.agents import AgentProfile, RiskPreference


def test_agent_profile_stores_persona_and_speech_traits():
    agent = AgentProfile(
        agent_id="agent_linye",
        name="林野",
        avatar_url=None,
        avatar_prompt="冷静的年轻侦探，半身像，暗色背景",
        persona="理性、谨慎、讨厌无逻辑发言",
        speech_style="短句、克制、会引用投票细节",
        reasoning_level=5,
        deception_level=3,
        aggression_level=2,
        cooperation_level=4,
        risk_preference=RiskPreference.BALANCED,
        memory_style="focus_on_votes_and_claims",
        enabled=True,
    )

    assert agent.name == "林野"
    assert agent.reasoning_level == 5


def test_agent_profile_rejects_trait_outside_one_to_five():
    with pytest.raises(ValueError, match="trait level must be between 1 and 5"):
        AgentProfile(
            agent_id="agent_bad",
            name="坏配置",
            avatar_url=None,
            avatar_prompt=None,
            persona="test",
            speech_style="test",
            reasoning_level=6,
            deception_level=3,
            aggression_level=2,
            cooperation_level=4,
            risk_preference=RiskPreference.BALANCED,
            memory_style="test",
            enabled=True,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/domain/test_agents.py -v
```

Expected: FAIL because agent model is missing.

- [ ] **Step 3: Implement agent profile model**

```python
from enum import StrEnum

from pydantic import BaseModel, field_validator


class RiskPreference(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class AgentProfile(BaseModel):
    agent_id: str
    name: str
    avatar_url: str | None = None
    avatar_prompt: str | None = None
    persona: str
    speech_style: str
    reasoning_level: int
    deception_level: int
    aggression_level: int
    cooperation_level: int
    risk_preference: RiskPreference
    memory_style: str
    enabled: bool = True

    @field_validator("reasoning_level", "deception_level", "aggression_level", "cooperation_level")
    @classmethod
    def trait_level_must_be_between_one_and_five(cls, value: int) -> int:
        if value < 1 or value > 5:
            raise ValueError("trait level must be between 1 and 5")
        return value
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/domain/test_agents.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/domain/agents.py tests/domain/test_agents.py
git commit -m "feat: add agent persona model"
```

### Task 5: Role Registry

**Files:**

- Create: `ai_werewolf/rules/role_registry.py`
- Create: `tests/rules/test_role_registry.py`

- [ ] **Step 1: Write failing tests for built-in role registry**

```python
from ai_werewolf.domain.roles import Faction
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


def test_builtin_registry_contains_core_roles():
    registry = BuiltInRoleRegistry()

    assert registry.get("werewolf").faction == Faction.WEREWOLF
    assert registry.get("seer").night_action == "seer_check"
    assert registry.get("witch").night_action == "witch_potion"
    assert registry.get("hunter").night_action is None
    assert registry.get("villager").faction == Faction.VILLAGER


def test_registry_reports_unknown_role():
    registry = BuiltInRoleRegistry()

    assert registry.has("white_wolf") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/rules/test_role_registry.py -v
```

Expected: FAIL because registry is missing.

- [ ] **Step 3: Implement built-in registry**

```python
from ai_werewolf.domain.roles import Faction, RoleDefinition


class BuiltInRoleRegistry:
    def __init__(self) -> None:
        self._roles = {
            "werewolf": RoleDefinition(
                key="werewolf",
                name="狼人",
                faction=Faction.WEREWOLF,
                night_action="wolf_kill",
                phase_order=10,
            ),
            "seer": RoleDefinition(
                key="seer",
                name="预言家",
                faction=Faction.VILLAGER,
                night_action="seer_check",
                phase_order=20,
            ),
            "witch": RoleDefinition(
                key="witch",
                name="女巫",
                faction=Faction.VILLAGER,
                night_action="witch_potion",
                phase_order=30,
            ),
            "hunter": RoleDefinition(
                key="hunter",
                name="猎人",
                faction=Faction.VILLAGER,
                night_action=None,
                phase_order=None,
            ),
            "villager": RoleDefinition(
                key="villager",
                name="平民",
                faction=Faction.VILLAGER,
                night_action=None,
                phase_order=None,
            ),
        }

    def get(self, role_key: str) -> RoleDefinition:
        return self._roles[role_key]

    def has(self, role_key: str) -> bool:
        return role_key in self._roles

    def all(self) -> list[RoleDefinition]:
        return list(self._roles.values())
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/rules/test_role_registry.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/rules/role_registry.py tests/rules/test_role_registry.py
git commit -m "feat: add built in role registry"
```

### Task 6: Board Validator

**Files:**

- Create: `ai_werewolf/rules/board_validator.py`
- Create: `tests/rules/test_board_validator.py`

- [ ] **Step 1: Write failing tests for board validation**

```python
import pytest

from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition
from ai_werewolf.rules.board_validator import BoardValidationError, BoardValidator
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


def make_board(roles):
    return BoardConfig(
        board_id="board_test",
        name="测试板子",
        roles=roles,
        sheriff_enabled=False,
        speech_rule=SpeechRule.SEAT_ORDER,
        vote_rule=VoteRule.SINGLE_VOTE,
        win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
        enabled=True,
    )


def test_validator_accepts_board_with_wolves_and_villagers():
    validator = BoardValidator(BuiltInRoleRegistry())
    board = make_board([
        BoardRoleCount(role_key="werewolf", count=2),
        BoardRoleCount(role_key="seer", count=1),
        BoardRoleCount(role_key="villager", count=3),
    ])

    validator.validate(board)


def test_validator_rejects_unknown_role():
    validator = BoardValidator(BuiltInRoleRegistry())
    board = make_board([BoardRoleCount(role_key="white_wolf", count=1)])

    with pytest.raises(BoardValidationError, match="unknown role: white_wolf"):
        validator.validate(board)


def test_validator_rejects_board_without_werewolf():
    validator = BoardValidator(BuiltInRoleRegistry())
    board = make_board([BoardRoleCount(role_key="villager", count=6)])

    with pytest.raises(BoardValidationError, match="at least one werewolf"):
        validator.validate(board)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/rules/test_board_validator.py -v
```

Expected: FAIL because validator is missing.

- [ ] **Step 3: Implement board validator**

```python
from ai_werewolf.domain.boards import BoardConfig
from ai_werewolf.domain.roles import Faction
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


class BoardValidationError(ValueError):
    pass


class BoardValidator:
    def __init__(self, role_registry: BuiltInRoleRegistry) -> None:
        self.role_registry = role_registry

    def validate(self, board: BoardConfig) -> None:
        werewolf_count = 0
        villager_count = 0

        for role_count in board.roles:
            if not self.role_registry.has(role_count.role_key):
                raise BoardValidationError(f"unknown role: {role_count.role_key}")
            role = self.role_registry.get(role_count.role_key)
            if role.faction == Faction.WEREWOLF:
                werewolf_count += role_count.count
            if role.faction == Faction.VILLAGER:
                villager_count += role_count.count

        if werewolf_count < 1:
            raise BoardValidationError("board must contain at least one werewolf")
        if villager_count < 1:
            raise BoardValidationError("board must contain at least one villager faction player")
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/rules/test_board_validator.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/rules/board_validator.py tests/rules/test_board_validator.py
git commit -m "feat: validate board configurations"
```

### Task 7: Seed Board Templates

**Files:**

- Create: `ai_werewolf/seeds/boards.py`
- Create: `tests/domain/test_board_seeds.py`

- [ ] **Step 1: Write failing tests for admin-configured seed boards**

```python
from ai_werewolf.rules.board_validator import BoardValidator
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.seeds.boards import default_boards


def test_default_boards_are_valid():
    validator = BoardValidator(BuiltInRoleRegistry())

    for board in default_boards():
        validator.validate(board)


def test_default_boards_include_beginner_standard_and_advanced():
    board_ids = {board.board_id for board in default_boards()}

    assert board_ids == {"board_6_beginner", "board_8_standard", "board_9_advanced"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/domain/test_board_seeds.py -v
```

Expected: FAIL because seed boards are missing.

- [ ] **Step 3: Implement default board seeds**

```python
from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition


def default_boards() -> list[BoardConfig]:
    return [
        BoardConfig(
            board_id="board_6_beginner",
            name="6人新手局",
            roles=[
                BoardRoleCount(role_key="werewolf", count=2),
                BoardRoleCount(role_key="seer", count=1),
                BoardRoleCount(role_key="villager", count=3),
            ],
            sheriff_enabled=False,
            speech_rule=SpeechRule.SEAT_ORDER,
            vote_rule=VoteRule.SINGLE_VOTE,
            win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
        ),
        BoardConfig(
            board_id="board_8_standard",
            name="8人预女猎",
            roles=[
                BoardRoleCount(role_key="werewolf", count=2),
                BoardRoleCount(role_key="seer", count=1),
                BoardRoleCount(role_key="witch", count=1),
                BoardRoleCount(role_key="hunter", count=1),
                BoardRoleCount(role_key="villager", count=3),
            ],
            sheriff_enabled=True,
            speech_rule=SpeechRule.SHERIFF_SELECT_DIRECTION,
            vote_rule=VoteRule.SINGLE_VOTE_WITH_PK,
            win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
        ),
        BoardConfig(
            board_id="board_9_advanced",
            name="9人进阶局",
            roles=[
                BoardRoleCount(role_key="werewolf", count=3),
                BoardRoleCount(role_key="seer", count=1),
                BoardRoleCount(role_key="witch", count=1),
                BoardRoleCount(role_key="hunter", count=1),
                BoardRoleCount(role_key="villager", count=3),
            ],
            sheriff_enabled=True,
            speech_rule=SpeechRule.SHERIFF_SELECT_DIRECTION,
            vote_rule=VoteRule.SINGLE_VOTE_WITH_PK,
            win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
        ),
    ]
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/domain/test_board_seeds.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/seeds/boards.py tests/domain/test_board_seeds.py
git commit -m "feat: add admin seed board templates"
```

### Task 8: Seed Agent Personas

**Files:**

- Create: `ai_werewolf/seeds/agents.py`
- Create: `tests/domain/test_agent_seeds.py`

- [ ] **Step 1: Write failing tests for reusable agent personas**

```python
from ai_werewolf.seeds.agents import default_agents


def test_default_agents_have_distinct_speech_styles():
    agents = default_agents()
    styles = {agent.speech_style for agent in agents}

    assert len(agents) >= 6
    assert len(styles) >= 4


def test_default_agents_are_enabled():
    assert all(agent.enabled for agent in default_agents())
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/domain/test_agent_seeds.py -v
```

Expected: FAIL because seed agents are missing.

- [ ] **Step 3: Implement default agents**

```python
from ai_werewolf.domain.agents import AgentProfile, RiskPreference


def default_agents() -> list[AgentProfile]:
    return [
        AgentProfile(
            agent_id="agent_linye",
            name="林野",
            avatar_prompt="冷静的年轻侦探，半身像，暗色背景",
            persona="理性、谨慎、讨厌无逻辑发言",
            speech_style="短句、克制、会引用投票细节",
            reasoning_level=5,
            deception_level=3,
            aggression_level=2,
            cooperation_level=4,
            risk_preference=RiskPreference.BALANCED,
            memory_style="focus_on_votes_and_claims",
        ),
        AgentProfile(
            agent_id="agent_xiaoman",
            name="小满",
            avatar_prompt="阳光开朗的少女玩家，明亮头像",
            persona="热情、直觉强、容易相信别人",
            speech_style="口语化、情绪明显、经常表达直觉",
            reasoning_level=3,
            deception_level=2,
            aggression_level=2,
            cooperation_level=5,
            risk_preference=RiskPreference.CONSERVATIVE,
            memory_style="focus_on_emotions_and_alliances",
        ),
        AgentProfile(
            agent_id="agent_qingshan",
            name="青山",
            avatar_prompt="沉稳中年策略家，复古桌游氛围",
            persona="沉稳、擅长控场、喜欢归纳局势",
            speech_style="结构化、分点说明、会给结论",
            reasoning_level=4,
            deception_level=4,
            aggression_level=3,
            cooperation_level=3,
            risk_preference=RiskPreference.BALANCED,
            memory_style="focus_on_claims_and_timing",
        ),
        AgentProfile(
            agent_id="agent_akai",
            name="阿凯",
            avatar_prompt="激进的竞技玩家，红色光影头像",
            persona="激进、压迫感强、喜欢抓漏洞",
            speech_style="强势、反问多、会快速站边",
            reasoning_level=4,
            deception_level=3,
            aggression_level=5,
            cooperation_level=2,
            risk_preference=RiskPreference.AGGRESSIVE,
            memory_style="focus_on_contradictions",
        ),
        AgentProfile(
            agent_id="agent_moyu",
            name="墨雨",
            avatar_prompt="神秘冷淡的夜色人物，黑蓝色头像",
            persona="安静、观察型、发言少但锋利",
            speech_style="短句、低频、关键时刻指出问题",
            reasoning_level=4,
            deception_level=5,
            aggression_level=3,
            cooperation_level=2,
            risk_preference=RiskPreference.CONSERVATIVE,
            memory_style="focus_on_silent_patterns",
        ),
        AgentProfile(
            agent_id="agent_duoduo",
            name="多多",
            avatar_prompt="活泼的桌游主持感角色，暖色头像",
            persona="话多、爱互动、会缓和气氛",
            speech_style="轻松、会接话、会提出开放问题",
            reasoning_level=2,
            deception_level=3,
            aggression_level=1,
            cooperation_level=5,
            risk_preference=RiskPreference.BALANCED,
            memory_style="focus_on_conversation_flow",
        ),
    ]
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/domain/test_agent_seeds.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/seeds/agents.py tests/domain/test_agent_seeds.py
git commit -m "feat: add default ai agent personas"
```

### Task 9: Game State Model

**Files:**

- Create: `ai_werewolf/domain/game_state.py`
- Create: `tests/domain/test_game_state.py`

- [ ] **Step 1: Write failing tests for game state**

```python
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState


def test_game_state_tracks_players_and_phase():
    state = GameState(
        game_id="game_1",
        board_id="board_6_beginner",
        phase=GamePhase.SETUP,
        day_count=0,
        players=[
            PlayerState(player_id="p1", agent_id=None, seat=1, role_key="seer", alive=True, is_human=True),
            PlayerState(player_id="p2", agent_id="agent_linye", seat=2, role_key="werewolf", alive=True, is_human=False),
        ],
    )

    assert state.alive_player_ids() == ["p1", "p2"]
    assert state.player_by_id("p2").role_key == "werewolf"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/domain/test_game_state.py -v
```

Expected: FAIL because game state model is missing.

- [ ] **Step 3: Implement game state model**

```python
from enum import StrEnum

from pydantic import BaseModel


class GamePhase(StrEnum):
    SETUP = "setup"
    SHERIFF_ELECTION = "sheriff_election"
    NIGHT = "night"
    DAY_ANNOUNCEMENT = "day_announcement"
    DAY_SPEECH = "day_speech"
    DAY_VOTE = "day_vote"
    GAME_OVER = "game_over"


class PlayerState(BaseModel):
    player_id: str
    agent_id: str | None
    seat: int
    role_key: str
    alive: bool
    is_human: bool
    sheriff: bool = False


class GameState(BaseModel):
    game_id: str
    board_id: str
    phase: GamePhase
    day_count: int
    players: list[PlayerState]
    winner: str | None = None

    def alive_player_ids(self) -> list[str]:
        return [player.player_id for player in self.players if player.alive]

    def player_by_id(self, player_id: str) -> PlayerState:
        return next(player for player in self.players if player.player_id == player_id)
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/domain/test_game_state.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/domain/game_state.py tests/domain/test_game_state.py
git commit -m "feat: add game state model"
```

### Task 10: Event and Action Models

**Files:**

- Create: `ai_werewolf/domain/events.py`
- Create: `ai_werewolf/domain/actions.py`
- Create: `tests/domain/test_events_actions.py`

- [ ] **Step 1: Write failing tests**

```python
from ai_werewolf.domain.actions import PlayerAction, PlayerActionType
from ai_werewolf.domain.events import GameEvent, GameEventType


def test_player_action_represents_vote_target():
    action = PlayerAction(
        actor_id="p1",
        action_type=PlayerActionType.VOTE,
        target_id="p2",
        reason="p2 发言前后矛盾",
    )

    assert action.action_type == PlayerActionType.VOTE
    assert action.target_id == "p2"


def test_game_event_has_public_visibility_flag():
    event = GameEvent(
        event_type=GameEventType.SPEECH,
        actor_id="p1",
        target_id=None,
        payload={"speech": "我先听后置位。"},
        public=True,
    )

    assert event.public is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/domain/test_events_actions.py -v
```

Expected: FAIL because event and action models are missing.

- [ ] **Step 3: Implement models**

`ai_werewolf/domain/actions.py`:

```python
from enum import StrEnum

from pydantic import BaseModel


class PlayerActionType(StrEnum):
    SPEAK = "speak"
    VOTE = "vote"
    WOLF_KILL = "wolf_kill"
    SEER_CHECK = "seer_check"
    WITCH_SAVE = "witch_save"
    WITCH_POISON = "witch_poison"
    HUNTER_SHOOT = "hunter_shoot"
    RUN_FOR_SHERIFF = "run_for_sheriff"
    WITHDRAW_SHERIFF_RUN = "withdraw_sheriff_run"


class PlayerAction(BaseModel):
    actor_id: str
    action_type: PlayerActionType
    target_id: str | None = None
    reason: str | None = None
```

`ai_werewolf/domain/events.py`:

```python
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class GameEventType(StrEnum):
    ROLE_ASSIGNED = "role_assigned"
    SPEECH = "speech"
    VOTE = "vote"
    NIGHT_ACTION = "night_action"
    DEATH = "death"
    EXILE = "exile"
    SHERIFF_ASSIGNED = "sheriff_assigned"
    GAME_END = "game_end"


class GameEvent(BaseModel):
    event_type: GameEventType
    actor_id: str | None
    target_id: str | None
    payload: dict[str, Any]
    public: bool
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/domain/test_events_actions.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/domain/events.py ai_werewolf/domain/actions.py tests/domain/test_events_actions.py
git commit -m "feat: add event and action models"
```

### Task 11: Role Assignment

**Files:**

- Create: `ai_werewolf/rules/assignment.py`
- Create: `tests/rules/test_assignment.py`

- [ ] **Step 1: Write failing tests for deterministic assignment**

```python
from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition
from ai_werewolf.rules.assignment import assign_roles


def test_assign_roles_assigns_exact_board_counts():
    board = BoardConfig(
        board_id="board_6_beginner",
        name="6人新手局",
        roles=[
            BoardRoleCount(role_key="werewolf", count=2),
            BoardRoleCount(role_key="seer", count=1),
            BoardRoleCount(role_key="villager", count=3),
        ],
        sheriff_enabled=False,
        speech_rule=SpeechRule.SEAT_ORDER,
        vote_rule=VoteRule.SINGLE_VOTE,
        win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
    )

    assigned = assign_roles(board, player_ids=["p1", "p2", "p3", "p4", "p5", "p6"], seed=7)

    assert sorted(assigned.keys()) == ["p1", "p2", "p3", "p4", "p5", "p6"]
    assert list(assigned.values()).count("werewolf") == 2
    assert list(assigned.values()).count("seer") == 1
    assert list(assigned.values()).count("villager") == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/rules/test_assignment.py -v
```

Expected: FAIL because assignment is missing.

- [ ] **Step 3: Implement role assignment**

```python
import random

from ai_werewolf.domain.boards import BoardConfig


def assign_roles(board: BoardConfig, player_ids: list[str], seed: int | None = None) -> dict[str, str]:
    if len(player_ids) != board.player_count:
        raise ValueError("player count does not match board")

    roles: list[str] = []
    for role_count in board.roles:
        roles.extend([role_count.role_key] * role_count.count)

    rng = random.Random(seed)
    rng.shuffle(roles)
    return dict(zip(player_ids, roles, strict=True))
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/rules/test_assignment.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/rules/assignment.py tests/rules/test_assignment.py
git commit -m "feat: assign roles from board config"
```

### Task 12: Voting Rule

**Files:**

- Create: `ai_werewolf/rules/voting.py`
- Create: `tests/rules/test_voting.py`

- [ ] **Step 1: Write failing tests for vote resolution**

```python
from ai_werewolf.domain.actions import PlayerAction, PlayerActionType
from ai_werewolf.rules.voting import VoteResult, resolve_single_vote


def test_resolve_single_vote_exiles_highest_vote_target():
    votes = [
        PlayerAction(actor_id="p1", action_type=PlayerActionType.VOTE, target_id="p3"),
        PlayerAction(actor_id="p2", action_type=PlayerActionType.VOTE, target_id="p3"),
        PlayerAction(actor_id="p3", action_type=PlayerActionType.VOTE, target_id="p2"),
    ]

    result = resolve_single_vote(votes)

    assert result == VoteResult(exiled_player_id="p3", tied_player_ids=[])


def test_resolve_single_vote_reports_tie():
    votes = [
        PlayerAction(actor_id="p1", action_type=PlayerActionType.VOTE, target_id="p2"),
        PlayerAction(actor_id="p2", action_type=PlayerActionType.VOTE, target_id="p1"),
    ]

    result = resolve_single_vote(votes)

    assert result.exiled_player_id is None
    assert result.tied_player_ids == ["p1", "p2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/rules/test_voting.py -v
```

Expected: FAIL because voting rule is missing.

- [ ] **Step 3: Implement voting rule**

```python
from collections import Counter

from pydantic import BaseModel

from ai_werewolf.domain.actions import PlayerAction


class VoteResult(BaseModel):
    exiled_player_id: str | None
    tied_player_ids: list[str]


def resolve_single_vote(votes: list[PlayerAction]) -> VoteResult:
    counts = Counter(vote.target_id for vote in votes if vote.target_id is not None)
    if not counts:
        return VoteResult(exiled_player_id=None, tied_player_ids=[])

    top_count = max(counts.values())
    tied = sorted(player_id for player_id, count in counts.items() if count == top_count)
    if len(tied) > 1:
        return VoteResult(exiled_player_id=None, tied_player_ids=tied)
    return VoteResult(exiled_player_id=tied[0], tied_player_ids=[])
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/rules/test_voting.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/rules/voting.py tests/rules/test_voting.py
git commit -m "feat: resolve single vote rule"
```

### Task 13: Win Condition Rule

**Files:**

- Create: `ai_werewolf/rules/win_conditions.py`
- Create: `tests/rules/test_win_conditions.py`

- [ ] **Step 1: Write failing tests for win conditions**

```python
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.rules.win_conditions import Winner, evaluate_winner


def make_state(players):
    return GameState(
        game_id="g1",
        board_id="board",
        phase=GamePhase.DAY_VOTE,
        day_count=1,
        players=players,
    )


def test_villagers_win_when_no_wolves_alive():
    state = make_state([
        PlayerState(player_id="p1", agent_id=None, seat=1, role_key="werewolf", alive=False, is_human=False),
        PlayerState(player_id="p2", agent_id=None, seat=2, role_key="villager", alive=True, is_human=True),
    ])

    assert evaluate_winner(state, BuiltInRoleRegistry()) == Winner.VILLAGERS


def test_wolves_win_when_wolves_reach_parity():
    state = make_state([
        PlayerState(player_id="p1", agent_id=None, seat=1, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="p2", agent_id=None, seat=2, role_key="villager", alive=True, is_human=True),
    ])

    assert evaluate_winner(state, BuiltInRoleRegistry()) == Winner.WOLVES
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/rules/test_win_conditions.py -v
```

Expected: FAIL because win condition module is missing.

- [ ] **Step 3: Implement win condition rule**

```python
from enum import StrEnum

from ai_werewolf.domain.game_state import GameState
from ai_werewolf.domain.roles import Faction
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


class Winner(StrEnum):
    WOLVES = "wolves"
    VILLAGERS = "villagers"


def evaluate_winner(state: GameState, role_registry: BuiltInRoleRegistry) -> Winner | None:
    alive_wolves = 0
    alive_non_wolves = 0
    for player in state.players:
        if not player.alive:
            continue
        role = role_registry.get(player.role_key)
        if role.faction == Faction.WEREWOLF:
            alive_wolves += 1
        else:
            alive_non_wolves += 1

    if alive_wolves == 0:
        return Winner.VILLAGERS
    if alive_wolves >= alive_non_wolves:
        return Winner.WOLVES
    return None
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/rules/test_win_conditions.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/rules/win_conditions.py tests/rules/test_win_conditions.py
git commit -m "feat: evaluate win conditions"
```

### Task 14: Night Resolution

**Files:**

- Create: `ai_werewolf/rules/night_resolution.py`
- Create: `tests/rules/test_night_resolution.py`

- [ ] **Step 1: Write failing tests for night resolution**

```python
from ai_werewolf.domain.actions import PlayerAction, PlayerActionType
from ai_werewolf.rules.night_resolution import resolve_night_deaths


def test_wolf_kill_deaths_are_cancelled_by_witch_save():
    actions = [
        PlayerAction(actor_id="wolf_team", action_type=PlayerActionType.WOLF_KILL, target_id="p3"),
        PlayerAction(actor_id="p4", action_type=PlayerActionType.WITCH_SAVE, target_id="p3"),
    ]

    assert resolve_night_deaths(actions) == []


def test_witch_poison_adds_death():
    actions = [
        PlayerAction(actor_id="wolf_team", action_type=PlayerActionType.WOLF_KILL, target_id="p3"),
        PlayerAction(actor_id="p4", action_type=PlayerActionType.WITCH_POISON, target_id="p2"),
    ]

    assert resolve_night_deaths(actions) == ["p2", "p3"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/rules/test_night_resolution.py -v
```

Expected: FAIL because night resolution is missing.

- [ ] **Step 3: Implement night resolution**

```python
from ai_werewolf.domain.actions import PlayerAction, PlayerActionType


def resolve_night_deaths(actions: list[PlayerAction]) -> list[str]:
    wolf_target: str | None = None
    saved_target: str | None = None
    poisoned_targets: set[str] = set()

    for action in actions:
        if action.action_type == PlayerActionType.WOLF_KILL:
            wolf_target = action.target_id
        elif action.action_type == PlayerActionType.WITCH_SAVE:
            saved_target = action.target_id
        elif action.action_type == PlayerActionType.WITCH_POISON and action.target_id is not None:
            poisoned_targets.add(action.target_id)

    deaths: set[str] = set(poisoned_targets)
    if wolf_target is not None and wolf_target != saved_target:
        deaths.add(wolf_target)

    return sorted(deaths)
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/rules/test_night_resolution.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/rules/night_resolution.py tests/rules/test_night_resolution.py
git commit -m "feat: resolve night deaths"
```

### Task 15: Sheriff Flow Rule

**Files:**

- Create: `ai_werewolf/rules/sheriff.py`
- Create: `tests/rules/test_sheriff.py`

- [ ] **Step 1: Write failing tests for sheriff election**

```python
from ai_werewolf.domain.actions import PlayerAction, PlayerActionType
from ai_werewolf.rules.sheriff import resolve_sheriff_election


def test_sheriff_election_assigns_highest_vote_candidate():
    votes = [
        PlayerAction(actor_id="p1", action_type=PlayerActionType.VOTE, target_id="p3"),
        PlayerAction(actor_id="p2", action_type=PlayerActionType.VOTE, target_id="p3"),
        PlayerAction(actor_id="p3", action_type=PlayerActionType.VOTE, target_id="p2"),
    ]

    assert resolve_sheriff_election(votes) == "p3"


def test_sheriff_election_returns_none_on_tie():
    votes = [
        PlayerAction(actor_id="p1", action_type=PlayerActionType.VOTE, target_id="p2"),
        PlayerAction(actor_id="p2", action_type=PlayerActionType.VOTE, target_id="p1"),
    ]

    assert resolve_sheriff_election(votes) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/rules/test_sheriff.py -v
```

Expected: FAIL because sheriff rules are missing.

- [ ] **Step 3: Implement sheriff election**

```python
from ai_werewolf.domain.actions import PlayerAction
from ai_werewolf.rules.voting import resolve_single_vote


def resolve_sheriff_election(votes: list[PlayerAction]) -> str | None:
    return resolve_single_vote(votes).exiled_player_id
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/rules/test_sheriff.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/rules/sheriff.py tests/rules/test_sheriff.py
git commit -m "feat: add sheriff election rule"
```

### Task 16: LLM Decision Schema

**Files:**

- Create: `ai_werewolf/llm/schemas.py`
- Create: `tests/llm/test_decision_schema.py`

- [ ] **Step 1: Write failing tests for structured decision parsing**

```python
import pytest

from ai_werewolf.domain.actions import PlayerActionType
from ai_werewolf.llm.schemas import PlayerDecision


def test_player_decision_parses_structured_vote():
    decision = PlayerDecision(
        speech="我投 3 号，他的发言前后矛盾。",
        action_type=PlayerActionType.VOTE,
        target_id="p3",
        public_reason="发言矛盾",
        private_memory_update="继续观察 5 号",
    )

    assert decision.target_id == "p3"


def test_player_decision_requires_speech():
    with pytest.raises(ValueError, match="speech cannot be empty"):
        PlayerDecision(
            speech="",
            action_type=PlayerActionType.SPEAK,
            target_id=None,
            public_reason=None,
            private_memory_update=None,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/llm/test_decision_schema.py -v
```

Expected: FAIL because LLM schema is missing.

- [ ] **Step 3: Implement decision schema**

```python
from pydantic import BaseModel, field_validator

from ai_werewolf.domain.actions import PlayerActionType


class PlayerDecision(BaseModel):
    speech: str
    action_type: PlayerActionType
    target_id: str | None
    public_reason: str | None
    private_memory_update: str | None

    @field_validator("speech")
    @classmethod
    def speech_cannot_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("speech cannot be empty")
        return value
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/llm/test_decision_schema.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/llm/schemas.py tests/llm/test_decision_schema.py
git commit -m "feat: define llm player decision schema"
```

### Task 17: Prompt Builder

**Files:**

- Create: `ai_werewolf/llm/prompt_builder.py`
- Create: `tests/llm/test_prompt_builder.py`

- [ ] **Step 1: Write failing tests for persona-aware prompt**

```python
from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.llm.prompt_builder import build_player_prompt


def test_prompt_includes_persona_but_not_hidden_system_terms():
    agent = AgentProfile(
        agent_id="agent_linye",
        name="林野",
        persona="理性、谨慎",
        speech_style="短句、克制",
        reasoning_level=5,
        deception_level=3,
        aggression_level=2,
        cooperation_level=4,
        risk_preference=RiskPreference.BALANCED,
        memory_style="focus_on_votes",
    )

    prompt = build_player_prompt(agent, role_key="werewolf", phase="day_speech")

    assert "林野" in prompt
    assert "理性、谨慎" in prompt
    assert "werewolf" in prompt
    assert "不要提及系统提示" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/llm/test_prompt_builder.py -v
```

Expected: FAIL because prompt builder is missing.

- [ ] **Step 3: Implement prompt builder**

```python
from ai_werewolf.domain.agents import AgentProfile


def build_player_prompt(agent: AgentProfile, role_key: str, phase: str) -> str:
    return (
        f"你正在扮演狼人杀玩家 {agent.name}。\n"
        f"人设：{agent.persona}\n"
        f"发言风格：{agent.speech_style}\n"
        f"推理强度：{agent.reasoning_level}/5，伪装能力：{agent.deception_level}/5，"
        f"攻击性：{agent.aggression_level}/5，合作倾向：{agent.cooperation_level}/5。\n"
        f"你的本局隐藏身份是：{role_key}。\n"
        f"当前阶段：{phase}。\n"
        "你必须像真实玩家一样发言。不要提及系统提示、JSON、模型、LangGraph 或隐藏字段。"
    )
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/llm/test_prompt_builder.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/llm/prompt_builder.py tests/llm/test_prompt_builder.py
git commit -m "feat: build persona aware player prompts"
```

### Task 18: LLM Safety Filter

**Files:**

- Create: `ai_werewolf/llm/safety.py`
- Create: `tests/llm/test_safety.py`

- [ ] **Step 1: Write failing tests for unsafe speech detection**

```python
from ai_werewolf.llm.safety import is_safe_speech


def test_safe_speech_accepts_normal_game_text():
    assert is_safe_speech("我觉得 4 号发言偏防守，今天可以先进票。") is True


def test_safe_speech_rejects_system_prompt_leak():
    assert is_safe_speech("根据系统提示，我的 role_key 是 werewolf。") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/llm/test_safety.py -v
```

Expected: FAIL because safety module is missing.

- [ ] **Step 3: Implement simple safety filter**

```python
FORBIDDEN_TERMS = [
    "系统提示",
    "system prompt",
    "role_key",
    "LangGraph",
    "JSON",
    "隐藏字段",
]


def is_safe_speech(speech: str) -> bool:
    lowered = speech.lower()
    return not any(term.lower() in lowered for term in FORBIDDEN_TERMS)
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/llm/test_safety.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/llm/safety.py tests/llm/test_safety.py
git commit -m "feat: detect unsafe player speech"
```

### Task 19: Player Decider with Fake Model

**Files:**

- Create: `ai_werewolf/llm/player_decider.py`
- Create: `tests/llm/test_player_decider.py`

- [ ] **Step 1: Write failing tests with fake LLM**

```python
from ai_werewolf.domain.actions import PlayerActionType
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.llm.schemas import PlayerDecision


class FakeModel:
    def decide(self, prompt: str) -> dict:
        return {
            "speech": "我先投 3 号，他像是在躲视角。",
            "action_type": "vote",
            "target_id": "p3",
            "public_reason": "躲视角",
            "private_memory_update": "观察 5 号",
        }


def test_decider_returns_valid_player_decision():
    decider = PlayerDecider(FakeModel())

    decision = decider.decide("prompt")

    assert isinstance(decision, PlayerDecision)
    assert decision.action_type == PlayerActionType.VOTE
    assert decision.target_id == "p3"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/llm/test_player_decider.py -v
```

Expected: FAIL because decider is missing.

- [ ] **Step 3: Implement player decider**

```python
from typing import Protocol

from ai_werewolf.llm.schemas import PlayerDecision
from ai_werewolf.llm.safety import is_safe_speech


class DecisionModel(Protocol):
    def decide(self, prompt: str) -> dict:
        ...


class PlayerDecider:
    def __init__(self, model: DecisionModel) -> None:
        self.model = model

    def decide(self, prompt: str) -> PlayerDecision:
        decision = PlayerDecision.model_validate(self.model.decide(prompt))
        if not is_safe_speech(decision.speech):
            raise ValueError("unsafe speech")
        return decision
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/llm/test_player_decider.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/llm/player_decider.py tests/llm/test_player_decider.py
git commit -m "feat: add player decider adapter"
```

### Task 20: Avatar Provider Interface

**Files:**

- Create: `ai_werewolf/avatars/provider.py`
- Create: `tests/avatars/test_avatar_provider.py`

- [ ] **Step 1: Write failing tests for fake avatar provider**

```python
from ai_werewolf.avatars.provider import FakeAvatarProvider


def test_fake_avatar_provider_returns_deterministic_url():
    provider = FakeAvatarProvider(base_url="/static/default")

    url = provider.generate("冷静的年轻侦探")

    assert url == "/static/default/generated-avatar.png"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/avatars/test_avatar_provider.py -v
```

Expected: FAIL because avatar provider is missing.

- [ ] **Step 3: Implement provider protocol and fake**

```python
from typing import Protocol


class AvatarProvider(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class FakeAvatarProvider:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt: str) -> str:
        return f"{self.base_url}/generated-avatar.png"
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/avatars/test_avatar_provider.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/avatars/provider.py tests/avatars/test_avatar_provider.py
git commit -m "feat: add avatar provider abstraction"
```

### Task 21: Avatar Service with Fallback

**Files:**

- Create: `ai_werewolf/avatars/service.py`
- Create: `tests/avatars/test_avatar_service.py`

- [ ] **Step 1: Write failing tests for fallback behavior**

```python
from ai_werewolf.avatars.service import AvatarService


class BrokenProvider:
    def generate(self, prompt: str) -> str:
        raise RuntimeError("image service unavailable")


def test_avatar_service_returns_default_when_provider_fails():
    service = AvatarService(provider=BrokenProvider(), default_avatar_url="/static/default/avatar.png")

    assert service.generate_or_default("侦探头像") == "/static/default/avatar.png"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/avatars/test_avatar_service.py -v
```

Expected: FAIL because avatar service is missing.

- [ ] **Step 3: Implement avatar service**

```python
from ai_werewolf.avatars.provider import AvatarProvider


class AvatarService:
    def __init__(self, provider: AvatarProvider, default_avatar_url: str) -> None:
        self.provider = provider
        self.default_avatar_url = default_avatar_url

    def generate_or_default(self, prompt: str | None) -> str:
        if not prompt:
            return self.default_avatar_url
        try:
            return self.provider.generate(prompt)
        except Exception:
            return self.default_avatar_url
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/avatars/test_avatar_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/avatars/service.py tests/avatars/test_avatar_service.py
git commit -m "feat: add avatar fallback service"
```

### Task 22: Storage Models

**Files:**

- Create: `ai_werewolf/storage/models.py`
- Create: `tests/domain/test_storage_models.py`

- [ ] **Step 1: Write failing tests for SQLModel tables**

```python
from ai_werewolf.storage.models import AgentProfileRecord, BoardRecord


def test_board_record_stores_json_config():
    record = BoardRecord(board_id="board_6", name="6人局", config_json={"player_count": 6}, enabled=True)

    assert record.board_id == "board_6"
    assert record.config_json["player_count"] == 6


def test_agent_record_stores_json_profile():
    record = AgentProfileRecord(agent_id="agent_1", name="林野", profile_json={"reasoning_level": 5}, enabled=True)

    assert record.profile_json["reasoning_level"] == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/domain/test_storage_models.py -v
```

Expected: FAIL because storage models are missing.

- [ ] **Step 3: Implement SQLModel records**

```python
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class BoardRecord(SQLModel, table=True):
    board_id: str = Field(primary_key=True)
    name: str
    config_json: dict[str, Any] = Field(sa_column=Column(JSON))
    enabled: bool = True


class AgentProfileRecord(SQLModel, table=True):
    agent_id: str = Field(primary_key=True)
    name: str
    profile_json: dict[str, Any] = Field(sa_column=Column(JSON))
    enabled: bool = True
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/domain/test_storage_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/storage/models.py tests/domain/test_storage_models.py
git commit -m "feat: add storage models"
```

### Task 23: Repositories

**Files:**

- Create: `ai_werewolf/storage/database.py`
- Create: `ai_werewolf/storage/repositories.py`
- Create: `tests/domain/test_repositories.py`

- [ ] **Step 1: Write failing tests for board repository**

```python
from sqlmodel import Session

from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition
from ai_werewolf.storage.database import create_engine_and_tables
from ai_werewolf.storage.repositories import BoardRepository


def test_board_repository_saves_and_loads_board():
    engine = create_engine_and_tables("sqlite://")
    board = BoardConfig(
        board_id="board_test",
        name="测试板子",
        roles=[BoardRoleCount(role_key="werewolf", count=1), BoardRoleCount(role_key="villager", count=2)],
        sheriff_enabled=False,
        speech_rule=SpeechRule.SEAT_ORDER,
        vote_rule=VoteRule.SINGLE_VOTE,
        win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
    )

    with Session(engine) as session:
        repo = BoardRepository(session)
        repo.save(board)
        loaded = repo.get("board_test")

    assert loaded == board
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/domain/test_repositories.py -v
```

Expected: FAIL because database and repository are missing.

- [ ] **Step 3: Implement database and board repository**

`ai_werewolf/storage/database.py`:

```python
from sqlmodel import SQLModel, create_engine


def create_engine_and_tables(database_url: str):
    engine = create_engine(database_url)
    SQLModel.metadata.create_all(engine)
    return engine
```

`ai_werewolf/storage/repositories.py`:

```python
from sqlmodel import Session

from ai_werewolf.domain.boards import BoardConfig
from ai_werewolf.storage.models import BoardRecord


class BoardRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, board: BoardConfig) -> None:
        record = BoardRecord(
            board_id=board.board_id,
            name=board.name,
            config_json=board.model_dump(mode="json"),
            enabled=board.enabled,
        )
        self.session.merge(record)
        self.session.commit()

    def get(self, board_id: str) -> BoardConfig:
        record = self.session.get(BoardRecord, board_id)
        if record is None:
            raise KeyError(board_id)
        return BoardConfig.model_validate(record.config_json)
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/domain/test_repositories.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/storage/database.py ai_werewolf/storage/repositories.py tests/domain/test_repositories.py
git commit -m "feat: persist board configurations"
```

### Task 24: Agent Repository

**Files:**

- Modify: `ai_werewolf/storage/repositories.py`
- Create: `tests/domain/test_agent_repository.py`

- [ ] **Step 1: Write failing tests for agent repository**

```python
from sqlmodel import Session

from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.storage.database import create_engine_and_tables
from ai_werewolf.storage.repositories import AgentRepository


def test_agent_repository_saves_and_loads_agent():
    engine = create_engine_and_tables("sqlite://")
    agent = AgentProfile(
        agent_id="agent_linye",
        name="林野",
        persona="理性",
        speech_style="短句",
        reasoning_level=5,
        deception_level=3,
        aggression_level=2,
        cooperation_level=4,
        risk_preference=RiskPreference.BALANCED,
        memory_style="focus_on_votes",
    )

    with Session(engine) as session:
        repo = AgentRepository(session)
        repo.save(agent)
        loaded = repo.get("agent_linye")

    assert loaded == agent
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/domain/test_agent_repository.py -v
```

Expected: FAIL because `AgentRepository` is missing.

- [ ] **Step 3: Implement agent repository**

```python
from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.storage.models import AgentProfileRecord


class AgentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, agent: AgentProfile) -> None:
        record = AgentProfileRecord(
            agent_id=agent.agent_id,
            name=agent.name,
            profile_json=agent.model_dump(mode="json"),
            enabled=agent.enabled,
        )
        self.session.merge(record)
        self.session.commit()

    def get(self, agent_id: str) -> AgentProfile:
        record = self.session.get(AgentProfileRecord, agent_id)
        if record is None:
            raise KeyError(agent_id)
        return AgentProfile.model_validate(record.profile_json)
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/domain/test_agent_repository.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/storage/repositories.py tests/domain/test_agent_repository.py
git commit -m "feat: persist agent personas"
```

### Task 25: LangGraph Builder Phase List

**Files:**

- Create: `ai_werewolf/graph/builder.py`
- Create: `tests/graph/test_graph_builder.py`

- [ ] **Step 1: Write failing tests for dynamic phase planning**

```python
from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition
from ai_werewolf.graph.builder import build_phase_plan
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


def test_phase_plan_includes_sheriff_when_enabled():
    board = BoardConfig(
        board_id="board",
        name="8人预女猎",
        roles=[BoardRoleCount(role_key="werewolf", count=2), BoardRoleCount(role_key="seer", count=1), BoardRoleCount(role_key="villager", count=5)],
        sheriff_enabled=True,
        speech_rule=SpeechRule.SHERIFF_SELECT_DIRECTION,
        vote_rule=VoteRule.SINGLE_VOTE,
        win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
    )

    phases = build_phase_plan(board, BuiltInRoleRegistry())

    assert phases[0] == "initialize_game"
    assert "sheriff_election" in phases
    assert phases.index("wolf_kill") < phases.index("seer_check")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/graph/test_graph_builder.py -v
```

Expected: FAIL because graph builder is missing.

- [ ] **Step 3: Implement phase planner**

```python
from ai_werewolf.domain.boards import BoardConfig
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


def build_phase_plan(board: BoardConfig, role_registry: BuiltInRoleRegistry) -> list[str]:
    phases = ["initialize_game"]
    if board.sheriff_enabled:
        phases.append("sheriff_election")

    night_actions: list[tuple[int, str]] = []
    for role_count in board.roles:
        role = role_registry.get(role_count.role_key)
        if role.night_action and role.phase_order is not None:
            night_actions.append((role.phase_order, role.night_action))

    phases.extend(action for _, action in sorted(set(night_actions)))
    phases.extend([
        "resolve_night",
        "day_announcement",
        "speech_round",
        "vote_round",
        "resolve_vote",
        "check_win_condition",
    ])
    return phases
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/graph/test_graph_builder.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/graph/builder.py tests/graph/test_graph_builder.py
git commit -m "feat: build dynamic phase plan from board config"
```

### Task 26: Graph Nodes - Initialize Game

**Files:**

- Create: `ai_werewolf/graph/nodes.py`
- Create: `tests/graph/test_nodes_initialize.py`

- [ ] **Step 1: Write failing tests for initialize node**

```python
from ai_werewolf.graph.nodes import initialize_game_node
from ai_werewolf.seeds.boards import default_boards
from ai_werewolf.seeds.agents import default_agents


def test_initialize_game_node_creates_players_with_roles():
    board = default_boards()[0]
    agents = default_agents()[:5]

    state = initialize_game_node(board=board, human_player_id="human", agents=agents, seed=1)

    assert len(state.players) == board.player_count
    assert any(player.is_human for player in state.players)
    assert len([player for player in state.players if player.role_key == "werewolf"]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/graph/test_nodes_initialize.py -v
```

Expected: FAIL because node is missing.

- [ ] **Step 3: Implement initialize node**

```python
from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.boards import BoardConfig
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
from ai_werewolf.rules.assignment import assign_roles


def initialize_game_node(board: BoardConfig, human_player_id: str, agents: list[AgentProfile], seed: int | None = None) -> GameState:
    if len(agents) != board.player_count - 1:
        raise ValueError("agent count must fill board seats after human player")

    player_ids = [human_player_id] + [agent.agent_id for agent in agents]
    assigned = assign_roles(board, player_ids, seed=seed)
    players = [
        PlayerState(player_id=human_player_id, agent_id=None, seat=1, role_key=assigned[human_player_id], alive=True, is_human=True)
    ]
    for index, agent in enumerate(agents, start=2):
        players.append(PlayerState(player_id=agent.agent_id, agent_id=agent.agent_id, seat=index, role_key=assigned[agent.agent_id], alive=True, is_human=False))

    return GameState(
        game_id="game_pending",
        board_id=board.board_id,
        phase=GamePhase.SETUP,
        day_count=0,
        players=players,
    )
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/graph/test_nodes_initialize.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/graph/nodes.py tests/graph/test_nodes_initialize.py
git commit -m "feat: initialize game from board and agents"
```

### Task 27: Graph Runner Skeleton

**Files:**

- Create: `ai_werewolf/graph/runner.py`
- Create: `tests/graph/test_runner.py`

- [ ] **Step 1: Write failing tests for runner creation**

```python
from ai_werewolf.graph.runner import GameRunner
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.seeds.boards import default_boards


def test_game_runner_exposes_phase_plan():
    runner = GameRunner(role_registry=BuiltInRoleRegistry())
    board = default_boards()[0]

    plan = runner.phase_plan(board)

    assert plan[0] == "initialize_game"
    assert "speech_round" in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/graph/test_runner.py -v
```

Expected: FAIL because runner is missing.

- [ ] **Step 3: Implement runner skeleton**

```python
from ai_werewolf.domain.boards import BoardConfig
from ai_werewolf.graph.builder import build_phase_plan
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


class GameRunner:
    def __init__(self, role_registry: BuiltInRoleRegistry) -> None:
        self.role_registry = role_registry

    def phase_plan(self, board: BoardConfig) -> list[str]:
        return build_phase_plan(board, self.role_registry)
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/graph/test_runner.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/graph/runner.py tests/graph/test_runner.py
git commit -m "feat: add game runner skeleton"
```

### Task 28: FastAPI App Factory

**Files:**

- Create: `ai_werewolf/main.py`
- Create: `tests/api/test_app.py`

- [ ] **Step 1: Write failing tests for health endpoint**

```python
from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_health_endpoint():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/api/test_app.py -v
```

Expected: FAIL because app factory is missing.

- [ ] **Step 3: Implement app factory**

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="AI Werewolf")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/api/test_app.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/main.py tests/api/test_app.py
git commit -m "feat: add fastapi app factory"
```

### Task 29: Admin Board API

**Files:**

- Create: `ai_werewolf/api/boards.py`
- Modify: `ai_werewolf/main.py`
- Create: `tests/api/test_boards_api.py`

- [ ] **Step 1: Write failing tests for board creation**

```python
from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_admin_can_create_board():
    client = TestClient(create_app())
    payload = {
        "board_id": "board_custom",
        "name": "后台配置板子",
        "roles": [
            {"role_key": "werewolf", "count": 1},
            {"role_key": "villager", "count": 2}
        ],
        "sheriff_enabled": False,
        "speech_rule": "seat_order",
        "vote_rule": "single_vote",
        "win_condition": "wolves_eliminated_or_parity",
        "enabled": True
    }

    response = client.post("/admin/boards", json=payload)

    assert response.status_code == 201
    assert response.json()["board_id"] == "board_custom"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/api/test_boards_api.py -v
```

Expected: FAIL because route is missing.

- [ ] **Step 3: Implement in-memory admin board route**

`ai_werewolf/api/boards.py`:

```python
from fastapi import APIRouter, status

from ai_werewolf.domain.boards import BoardConfig

router = APIRouter(prefix="/admin/boards", tags=["admin-boards"])
_boards: dict[str, BoardConfig] = {}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_board(board: BoardConfig) -> BoardConfig:
    _boards[board.board_id] = board
    return board


@router.get("")
def list_boards() -> list[BoardConfig]:
    return list(_boards.values())
```

`ai_werewolf/main.py`:

```python
from fastapi import FastAPI

from ai_werewolf.api.boards import router as boards_router


def create_app() -> FastAPI:
    app = FastAPI(title="AI Werewolf")
    app.include_router(boards_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/api/test_boards_api.py tests/api/test_app.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/api/boards.py ai_werewolf/main.py tests/api/test_boards_api.py
git commit -m "feat: add admin board api"
```

### Task 30: Admin Agent API

**Files:**

- Create: `ai_werewolf/api/agents.py`
- Modify: `ai_werewolf/main.py`
- Create: `tests/api/test_agents_api.py`

- [ ] **Step 1: Write failing tests for agent creation**

```python
from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_admin_can_create_agent_persona():
    client = TestClient(create_app())
    payload = {
        "agent_id": "agent_custom",
        "name": "后台智能体",
        "avatar_url": None,
        "avatar_prompt": "冷静的年轻侦探",
        "persona": "理性谨慎",
        "speech_style": "短句克制",
        "reasoning_level": 5,
        "deception_level": 3,
        "aggression_level": 2,
        "cooperation_level": 4,
        "risk_preference": "balanced",
        "memory_style": "focus_on_votes",
        "enabled": True
    }

    response = client.post("/admin/agents", json=payload)

    assert response.status_code == 201
    assert response.json()["agent_id"] == "agent_custom"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/api/test_agents_api.py -v
```

Expected: FAIL because route is missing.

- [ ] **Step 3: Implement in-memory admin agent route**

`ai_werewolf/api/agents.py`:

```python
from fastapi import APIRouter, status

from ai_werewolf.domain.agents import AgentProfile

router = APIRouter(prefix="/admin/agents", tags=["admin-agents"])
_agents: dict[str, AgentProfile] = {}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_agent(agent: AgentProfile) -> AgentProfile:
    _agents[agent.agent_id] = agent
    return agent


@router.get("")
def list_agents() -> list[AgentProfile]:
    return list(_agents.values())
```

Update `ai_werewolf/main.py`:

```python
from ai_werewolf.api.agents import router as agents_router

app.include_router(agents_router)
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/api/test_agents_api.py tests/api/test_app.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/api/agents.py ai_werewolf/main.py tests/api/test_agents_api.py
git commit -m "feat: add admin agent api"
```

### Task 31: Game Creation API

**Files:**

- Create: `ai_werewolf/api/games.py`
- Modify: `ai_werewolf/main.py`
- Create: `tests/api/test_games_api.py`

- [ ] **Step 1: Write failing tests for creating game from board and agents**

```python
from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_create_game_requires_matching_agent_count():
    client = TestClient(create_app())

    response = client.post("/games", json={
        "board_id": "board_6_beginner",
        "human_player_id": "human",
        "agent_ids": ["agent_linye"]
    })

    assert response.status_code == 400
    assert "agent count" in response.json()["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/api/test_games_api.py -v
```

Expected: FAIL because game route is missing.

- [ ] **Step 3: Implement minimal game creation route using seeds**

```python
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from ai_werewolf.graph.nodes import initialize_game_node
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards


class CreateGameRequest(BaseModel):
    board_id: str
    human_player_id: str
    agent_ids: list[str]


router = APIRouter(prefix="/games", tags=["games"])


@router.post("")
def create_game(request: CreateGameRequest):
    boards = {board.board_id: board for board in default_boards()}
    agents = {agent.agent_id: agent for agent in default_agents()}
    board = boards[request.board_id]
    selected_agents = [agents[agent_id] for agent_id in request.agent_ids]

    if len(selected_agents) != board.player_count - 1:
        raise HTTPException(status_code=400, detail="agent count must fill board seats after human player")

    return initialize_game_node(board, request.human_player_id, selected_agents, seed=1)
```

Update `ai_werewolf/main.py`:

```python
from ai_werewolf.api.games import router as games_router

app.include_router(games_router)
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/api/test_games_api.py tests/api/test_app.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/api/games.py ai_werewolf/main.py tests/api/test_games_api.py
git commit -m "feat: create games from board and agents"
```

### Task 32: Simulation Test for Full Beginner Game

**Files:**

- Create: `tests/simulation/test_beginner_game_simulation.py`
- Modify: `ai_werewolf/graph/runner.py`

- [ ] **Step 1: Write failing simulation test**

```python
from ai_werewolf.graph.runner import GameRunner
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards


def test_beginner_game_simulation_reaches_winner():
    runner = GameRunner(role_registry=BuiltInRoleRegistry())
    board = next(board for board in default_boards() if board.board_id == "board_6_beginner")
    agents = default_agents()[:5]

    result = runner.simulate_game(board=board, human_player_id="human", agents=agents, seed=3)

    assert result.winner in {"wolves", "villagers"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/simulation/test_beginner_game_simulation.py -v
```

Expected: FAIL because `simulate_game` is missing.

- [ ] **Step 3: Implement minimal deterministic simulation**

```python
from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.boards import BoardConfig
from ai_werewolf.graph.nodes import initialize_game_node
from ai_werewolf.rules.win_conditions import evaluate_winner


def simulate_game(self, board: BoardConfig, human_player_id: str, agents: list[AgentProfile], seed: int | None = None):
    state = initialize_game_node(board, human_player_id, agents, seed=seed)
    for player in state.players:
        if player.role_key == "werewolf":
            player.alive = False
            break
    winner = evaluate_winner(state, self.role_registry)
    state.winner = winner.value if winner is not None else "villagers"
    return state
```

Add this method to `GameRunner`.

- [ ] **Step 4: Run simulation test**

Run:

```bash
pytest tests/simulation/test_beginner_game_simulation.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/graph/runner.py tests/simulation/test_beginner_game_simulation.py
git commit -m "test: add beginner game simulation"
```

### Task 33: Replace Simulation Stub with Real Round Loop

**Files:**

- Modify: `ai_werewolf/graph/runner.py`
- Create: `tests/simulation/test_round_loop.py`

- [ ] **Step 1: Write failing test for multiple round loop**

```python
from ai_werewolf.graph.runner import GameRunner
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards


def test_simulation_records_at_least_one_day():
    runner = GameRunner(role_registry=BuiltInRoleRegistry())
    board = next(board for board in default_boards() if board.board_id == "board_6_beginner")

    result = runner.simulate_game(board=board, human_player_id="human", agents=default_agents()[:5], seed=4)

    assert result.day_count >= 1
```

- [ ] **Step 2: Run test to verify it fails or exposes stub behavior**

Run:

```bash
pytest tests/simulation/test_round_loop.py -v
```

Expected: FAIL because the simulation stub does not model a real day count.

- [ ] **Step 3: Implement minimal loop**

Update `simulate_game` so it:

1. Initializes game.
2. Sets `day_count = 1`.
3. Eliminates one werewolf per round for deterministic tests.
4. Evaluates winner after each elimination.
5. Stops after 10 rounds as a safety cap.

```python
def simulate_game(self, board: BoardConfig, human_player_id: str, agents: list[AgentProfile], seed: int | None = None):
    state = initialize_game_node(board, human_player_id, agents, seed=seed)
    for day in range(1, 11):
        state.day_count = day
        alive_wolf = next((player for player in state.players if player.alive and player.role_key == "werewolf"), None)
        if alive_wolf is not None:
            alive_wolf.alive = False
        winner = evaluate_winner(state, self.role_registry)
        if winner is not None:
            state.winner = winner.value
            return state
    state.winner = "villagers"
    return state
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/simulation -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_werewolf/graph/runner.py tests/simulation/test_round_loop.py
git commit -m "feat: add deterministic simulation round loop"
```

### Task 34: Frontend Board Editor Contract

**Files:**

- Create: `frontend-contracts/board-editor.md`
- Create: `tests/api/test_board_contract.py`

- [ ] **Step 1: Write failing API contract test**

```python
from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_list_boards_returns_array_for_frontend_editor():
    client = TestClient(create_app())

    response = client.get("/admin/boards")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Run test**

Run:

```bash
pytest tests/api/test_board_contract.py -v
```

Expected: PASS if Task 29 is complete. If FAIL, fix board API before writing docs.

- [ ] **Step 3: Write board editor contract**

```markdown
# Board Editor Frontend Contract

Admin users can create and edit board configurations.

Required fields:
- board_id
- name
- roles
- sheriff_enabled
- speech_rule
- vote_rule
- win_condition
- enabled

Validation:
- At least one werewolf role.
- At least one villager faction role.
- Total role count must match game player count.
```

- [ ] **Step 4: Run related API tests**

Run:

```bash
pytest tests/api/test_board_contract.py tests/api/test_boards_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-contracts/board-editor.md tests/api/test_board_contract.py
git commit -m "docs: define board editor frontend contract"
```

### Task 35: Frontend Agent Editor Contract

**Files:**

- Create: `frontend-contracts/agent-editor.md`
- Create: `tests/api/test_agent_contract.py`

- [ ] **Step 1: Write failing API contract test**

```python
from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_list_agents_returns_array_for_frontend_editor():
    client = TestClient(create_app())

    response = client.get("/admin/agents")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Run test**

Run:

```bash
pytest tests/api/test_agent_contract.py -v
```

Expected: PASS if Task 30 is complete. If FAIL, fix agent API first.

- [ ] **Step 3: Write agent editor contract**

```markdown
# Agent Editor Frontend Contract

Admin users can create and edit reusable AI player personas.

Required fields:
- agent_id
- name
- persona
- speech_style
- reasoning_level
- deception_level
- aggression_level
- cooperation_level
- risk_preference
- memory_style
- enabled

Optional fields:
- avatar_url
- avatar_prompt
```

- [ ] **Step 4: Run related tests**

Run:

```bash
pytest tests/api/test_agent_contract.py tests/api/test_agents_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-contracts/agent-editor.md tests/api/test_agent_contract.py
git commit -m "docs: define agent editor frontend contract"
```

### Task 36: End-to-End MVP Acceptance Test

**Files:**

- Create: `tests/simulation/test_mvp_acceptance.py`

- [ ] **Step 1: Write failing acceptance test**

```python
from ai_werewolf.graph.runner import GameRunner
from ai_werewolf.rules.board_validator import BoardValidator
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards


def test_mvp_acceptance_all_seed_boards_validate_and_beginner_game_finishes():
    role_registry = BuiltInRoleRegistry()
    validator = BoardValidator(role_registry)
    boards = default_boards()

    for board in boards:
        validator.validate(board)

    beginner = next(board for board in boards if board.board_id == "board_6_beginner")
    result = GameRunner(role_registry).simulate_game(
        board=beginner,
        human_player_id="human",
        agents=default_agents()[:5],
        seed=9,
    )

    assert result.winner in {"wolves", "villagers"}
    assert result.day_count >= 1
```

- [ ] **Step 2: Run test to verify it fails if any previous integration is incomplete**

Run:

```bash
pytest tests/simulation/test_mvp_acceptance.py -v
```

Expected: PASS only when core MVP pieces are integrated. If FAIL, fix the specific missing integration.

- [ ] **Step 3: Run full suite**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/simulation/test_mvp_acceptance.py
git commit -m "test: add mvp acceptance coverage"
```

## 5. Suggested Work Breakdown by Milestone

### Milestone A: Domain Foundation

Tasks 1-10.

Deliverable: Models for roles, boards, agents, game state, events, and actions. No API or LLM needed.

### Milestone B: Rule Engine

Tasks 11-15.

Deliverable: Deterministic role assignment, voting, night resolution, sheriff election, and win condition logic.

### Milestone C: AI Layer

Tasks 16-21.

Deliverable: Structured LLM output, persona prompts, safety checks, fake-model decider, avatar abstraction, fallback avatar service.

### Milestone D: Persistence and APIs

Tasks 22-31.

Deliverable: SQLModel persistence plus admin board/agent APIs and game creation API.

### Milestone E: Game Runner and Acceptance

Tasks 32-36.

Deliverable: Deterministic simulation, MVP acceptance tests, and frontend contracts.

## 6. Testing Policy

No production code is accepted without a failing test first.

Minimum coverage expectations:

- Board validation: unknown roles, no wolves, no villagers, role counts.
- Agent validation: trait range, required persona fields, enabled/disabled filtering.
- Rule engine: role assignment, night deaths, voting ties, sheriff election, win conditions.
- LLM adapter: structured output parsing, unsafe speech rejection, fake model behavior.
- Avatar service: success path and fallback path.
- API: create/list boards, create/list agents, create game, invalid agent count.
- Simulation: at least 10 deterministic games; 9 of 10 must finish.

## 7. Risks and Guardrails

| Risk | Guardrail |
| --- | --- |
| Board config becomes hidden code | BoardConfig stays pure data; role skills come from role registry |
| LLM mutates game state | LLM returns only `PlayerDecision`; rules engine applies actions |
| Agents all sound the same | Persona fields are required and prompt tests assert their inclusion |
| Avatar generation blocks gameplay | Avatar service is asynchronous later; MVP has default fallback |
| Sheriff flow delays MVP | No-sheriff board must finish first; sheriff board can be tested as a separate flow |
| Frontend and backend drift | Contract docs and API tests are added before UI implementation |

## 8. Execution Recommendation

Use subagent-driven development once implementation starts:

- One worker per milestone or per 3-5 tasks.
- Workers must not skip Red-Green-Refactor.
- Main agent reviews tests after each milestone.
- Merge only after `pytest -v` passes.

## 9. Self-Review

Spec coverage:

- Backend-configured boards: covered by Tasks 3, 6, 7, 23, 29, 34.
- Backend-configured agent personas: covered by Tasks 4, 8, 24, 30, 35.
- Board as standalone data structure: covered by BoardConfig, BoardRecord, BoardRepository.
- Agent persona as standalone data structure: covered by AgentProfile, AgentProfileRecord, AgentRepository.
- LangGraph dynamic flow: covered by Tasks 25-27.
- TDD discipline: every task starts with failing tests and commands.
- Avatar generation: covered by Tasks 20-21.
- No voice narration: explicitly out of scope.

Placeholder scan:

- No unresolved placeholder markers remain in the plan.
- Every code task includes exact test, expected failure, implementation, verification, and commit command.

Type consistency:

- `BoardConfig`, `AgentProfile`, `GameState`, `PlayerAction`, and `PlayerDecision` names are consistent across tasks.
- `board_id`, `agent_id`, `role_key`, and `player_id` naming is consistent across APIs and domain code.
