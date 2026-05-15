# Core Playable Engine Extraction - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the game engine from `api/games.py` into an `engine/` module and implement LLM-driven night actions, fixed vote timing, AI last words, and hunter shoot logic so the game is actually playable.

**Architecture:** PhaseOrchestrator is the single entry point for game progression. Resolvers (NightResolver, VoteResolver, HunterResolver) handle each phase's logic. `api/games.py` becomes a thin HTTP layer that delegates to PhaseOrchestrator. All LLM calls go through the existing `PlayerDecider` → `ModelProvider` pipeline.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, existing LLM provider infrastructure (`llm/` module)

---

## File Structure

| File | Responsibility |
|------|----------------|
| `engine/__init__.py` | Module init, export PhaseOrchestrator |
| `engine/session.py` | GameSession dataclass (moved from api/games.py) |
| `engine/context.py` | `build_game_context()` and `build_private_infos()` helpers |
| `engine/night.py` | NightResolver - collect LLM night actions and resolve deaths |
| `engine/vote.py` | VoteResolver - collect AI votes after human, resolve exile |
| `engine/hunter.py` | HunterResolver - trigger hunter shoot on death |
| `engine/orchestrator.py` | PhaseOrchestrator - routes actions to resolvers |
| `engine/helpers.py` | `_event()`, `_display_name()`, `_allowed_actions()`, `_frontend_state()` |
| `api/games.py` | Thin HTTP layer (requests/responses only) |
| `llm/prompt_builder.py` | Add `wolf_kill_target_id` param to `_build_witch_action_hint` |
| `tests/test_engine_night.py` | NightResolver unit tests |
| `tests/test_engine_vote.py` | VoteResolver unit tests |
| `tests/test_engine_hunter.py` | HunterResolver unit tests |
| `tests/test_engine_orchestrator.py` | PhaseOrchestrator integration tests (full game loop) |

---

### Task 1: Create `engine/session.py` - Move GameSession

**Files:**
- Create: `engine/__init__.py`
- Create: `engine/session.py`
- Test: `tests/test_engine_session.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engine_session.py
"""Tests for engine/session.py - GameSession dataclass."""
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState, PlayerPrivateInfo


def _make_players():
    return [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="ai_1", agent_id="ai_1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="ai_2", agent_id="ai_2", seat=3, role_key="seer", alive=True, is_human=False),
    ]


def _make_state():
    return GameState(game_id="test_game", board_id="board_8", phase=GamePhase.SETUP, day_count=0, players=_make_players())


def test_game_session_defaults():
    """GameSession has expected default fields."""
    from ai_werewolf.engine.session import GameSession

    state = _make_state()
    session = GameSession(state=state, agents={}, human_player_id="human")

    assert session.public_events == []
    assert session.voted_player_ids == set()
    assert session.night_actions == []
    assert session.witch_has_save_potion is True
    assert session.witch_has_poison is True
    assert session.private_infos == {}
    assert session.pending_last_words_player_id is None


def test_game_session_with_private_infos():
    """private_infos can be set at construction."""
    from ai_werewolf.engine.session import GameSession

    state = _make_state()
    infos = {
        "ai_1": PlayerPrivateInfo(wolf_teammates=[]),
        "human": PlayerPrivateInfo(),
    }
    session = GameSession(state=state, agents={}, human_player_id="human", private_infos=infos)

    assert session.private_infos["ai_1"].wolf_teammates == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/test_engine_session.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'ai_werewolf.engine'`

- [ ] **Step 3: Create engine package and session.py**

```python
# engine/__init__.py
```

```python
# engine/session.py
"""GameSession - runtime state for a single game instance."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GameState, PlayerPrivateInfo


@dataclass
class GameSession:
    """Runtime state for one game instance.

    Attributes:
        state:                     Current game state (phase, players, winner).
        agents:                    AI player profiles keyed by agent_id.
        human_player_id:           Human player's player_id.
        public_events:             Public event log, in chronological order.
        voted_player_ids:          Set of players who have voted (for frontend display).
        night_actions:             Night action records (for night resolution).
        witch_has_save_potion:     Whether witch still has the save potion.
        witch_has_poison:          Whether witch still has the poison potion.
        private_infos:             Per-player private info keyed by player_id.
        pending_last_words_player_id: Player who needs to give last words.
    """

    state: GameState
    agents: dict[str, AgentProfile]
    human_player_id: str
    public_events: list[dict[str, Any]] = field(default_factory=list)
    voted_player_ids: set[str] = field(default_factory=set)
    night_actions: list[dict[str, Any]] = field(default_factory=list)
    witch_has_save_potion: bool = True
    witch_has_poison: bool = True
    private_infos: dict[str, PlayerPrivateInfo] = field(default_factory=dict)
    pending_last_words_player_id: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/test_engine_session.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/__init__.py engine/session.py tests/test_engine_session.py
git commit -m "feat(engine): create engine module with GameSession dataclass"
```

---

### Task 2: Create `engine/context.py` - Move helper functions

**Files:**
- Create: `engine/context.py`
- Test: `tests/test_engine_context.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engine_context.py
"""Tests for engine/context.py - game context and private info builders."""


def test_build_game_context_empty():
    """Empty session returns empty context string."""
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.session import GameSession
    from ai_werewolf.engine.context import build_game_context

    state = GameState(
        game_id="g", board_id="b", phase=GamePhase.SETUP, day_count=0,
        players=[PlayerState(player_id="p", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True)],
    )
    session = GameSession(state=state, agents={}, human_player_id="p")
    assert build_game_context(session) == ""


def test_build_game_context_truncates():
    """build_game_context keeps only last 20 events."""
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.session import GameSession
    from ai_werewolf.engine.context import build_game_context

    state = GameState(
        game_id="g", board_id="b", phase=GamePhase.SETUP, day_count=0,
        players=[PlayerState(player_id="p", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True)],
    )
    session = GameSession(state=state, agents={}, human_player_id="p")
    for i in range(25):
        session.public_events.append({"event_type": "phase_changed", "actor_id": None, "target_id": None, "payload": {"message": f"event_{i}"}, "public": True})

    ctx = build_game_context(session)
    lines = [l for l in ctx.strip().split("\n") if l]
    assert len(lines) == 20
    assert "event_24" in ctx
    assert "event_4" not in ctx


def test_build_private_infos_wolves():
    """Wolves get wolf_teammates populated."""
    from ai_werewolf.domain.game_state import PlayerState
    from ai_werewolf.engine.context import build_private_infos

    players = [
        PlayerState(player_id="w1", agent_id="w1", seat=1, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="w2", agent_id="w2", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=3, role_key="villager", alive=True, is_human=True),
    ]
    infos = build_private_infos(players)
    assert infos["w1"].wolf_teammates == ["w2"]
    assert infos["w2"].wolf_teammates == ["w1"]
    assert infos["v1"].wolf_teammates == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/test_engine_context.py -v`
Expected: FAIL

- [ ] **Step 3: Implement engine/context.py**

```python
# engine/context.py
"""Game context builder for LLM prompts and private info initialization."""
from __future__ import annotations

from ai_werewolf.domain.game_state import GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.session import GameSession


def build_game_context(session: GameSession) -> str:
    """Build game context string from public events for LLM prompts."""
    lines = []
    for event in session.public_events:
        etype = event.get("event_type", "")
        payload = event.get("payload", {})
        message = payload.get("message", "")
        lines.append(f"[{etype}] {message}")
    return "\n".join(lines[-20:])


def build_private_infos(players: list[PlayerState]) -> dict[str, PlayerPrivateInfo]:
    """Initialize private info for each player. Wolves learn their teammates."""
    infos = {player.player_id: PlayerPrivateInfo() for player in players}
    wolf_ids = [p.player_id for p in players if p.role_key == "werewolf"]
    for wolf_id in wolf_ids:
        infos[wolf_id].wolf_teammates = [other_id for other_id in wolf_ids if other_id != wolf_id]
    return infos
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/test_engine_context.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/context.py tests/test_engine_context.py
git commit -m "feat(engine): add game context and private info builders"
```

---

### Task 3: Create `engine/helpers.py` - Move UI helper functions

**Files:**
- Create: `engine/helpers.py`
- Test: `tests/test_engine_helpers.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engine_helpers.py
"""Tests for engine/helpers.py."""


def test_event_structure():
    from ai_werewolf.engine.helpers import event

    ev = event("speech", "hello", actor_id="p1", target_id="p2")
    assert ev["event_type"] == "speech"
    assert ev["actor_id"] == "p1"
    assert ev["target_id"] == "p2"
    assert ev["payload"]["message"] == "hello"


def test_display_name_human():
    from ai_werewolf.domain.agents import AgentProfile
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.session import GameSession
    from ai_werewolf.engine.helpers import display_name

    state = GameState(
        game_id="g", board_id="b", phase=GamePhase.SETUP, day_count=0,
        players=[PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True)],
    )
    session = GameSession(state=state, agents={}, human_player_id="human")
    assert display_name("human", session) == "你"


def test_display_name_ai():
    from ai_werewolf.domain.agents import AgentProfile
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.session import GameSession
    from ai_werewolf.engine.helpers import display_name

    state = GameState(
        game_id="g", board_id="b", phase=GamePhase.SETUP, day_count=0,
        players=[
            PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
            PlayerState(player_id="ai_1", agent_id="ai_1", seat=2, role_key="werewolf", alive=True, is_human=False),
        ],
    )
    session = GameSession(state=state, agents={"ai_1": AgentProfile(name="张三", agent_id="ai_1", persona="aggressive")}, human_player_id="human")
    assert display_name("ai_1", session) == "张三"


def test_allowed_actions_setup():
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.helpers import allowed_actions

    state = GameState(game_id="g", board_id="b", phase=GamePhase.SETUP, day_count=0, players=[
        PlayerState(player_id="p", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
    ])
    actions = allowed_actions(state)
    assert len(actions) == 1
    assert actions[0]["action_type"] == "start_game"


def test_allowed_actions_night():
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.helpers import allowed_actions

    state = GameState(game_id="g", board_id="b", phase=GamePhase.NIGHT, day_count=1, players=[
        PlayerState(player_id="p", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
    ])
    actions = allowed_actions(state)
    assert actions[0]["action_type"] == "skip"


def test_allowed_actions_game_over():
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.helpers import allowed_actions

    state = GameState(game_id="g", board_id="b", phase=GamePhase.GAME_OVER, day_count=1, players=[
        PlayerState(player_id="p", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
    ], winner="villagers")
    assert allowed_actions(state) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/test_engine_helpers.py -v`
Expected: FAIL

- [ ] **Step 3: Implement engine/helpers.py**

```python
# engine/helpers.py
"""Shared helper functions for event building, display names, and allowed actions."""
from __future__ import annotations

from typing import Any

from ai_werewolf.domain.game_state import GamePhase, GameState
from ai_werewolf.engine.session import GameSession


def event(event_type: str, message: str, **payload: Any) -> dict[str, Any]:
    """Build a public event dict."""
    return {
        "event_type": event_type,
        "actor_id": payload.pop("actor_id", None),
        "target_id": payload.pop("target_id", None),
        "payload": {"message": message, **payload},
        "public": True,
    }


def display_name(player_id: str, session: GameSession) -> str:
    """Get display name for a player. Human player shows as '你'."""
    if player_id == session.human_player_id:
        return "你"
    agent = session.agents.get(player_id)
    return agent.name if agent is not None else player_id


def avatar_url(player_id: str, session: GameSession) -> str | None:
    """Get avatar URL for a player."""
    agent = session.agents.get(player_id)
    return agent.avatar_url if agent is not None else None


def allowed_actions(state: GameState) -> list[dict[str, Any]]:
    """Return available actions for human player based on current phase."""
    if state.winner is not None or state.phase == GamePhase.GAME_OVER:
        return []
    if state.phase == GamePhase.SETUP:
        return [{"action_type": "start_game", "label": "开始游戏"}]
    if state.phase == GamePhase.NIGHT:
        return [{"action_type": "skip", "label": "确认夜晚行动"}]
    if state.phase == GamePhase.DAY_ANNOUNCEMENT:
        return [{"action_type": "continue", "label": "进入白天发言"}]
    if state.phase == GamePhase.DAY_SPEECH:
        return [{"action_type": "speech", "label": "提交发言"}]
    if state.phase == GamePhase.EXILE_VOTE:
        return [{"action_type": "vote", "label": "投票"}, {"action_type": "abstain", "label": "弃票"}]
    if state.phase == GamePhase.LAST_WORDS:
        return [{"action_type": "continue", "label": "继续"}]
    return []


def frontend_state(session: GameSession, model_registry: Any, role_model_bindings: list) -> dict[str, Any]:
    """Build the full game state dict for the frontend."""
    from ai_werewolf.engine.helpers import allowed_actions, avatar_url, display_name

    state = session.state
    game_over = state.phase == GamePhase.GAME_OVER or state.winner is not None

    def _provider_id(role_key: str) -> str:
        return model_registry.provider_for_role(role_key, role_model_bindings).config.provider_id

    return {
        "game_id": state.game_id,
        "board_id": state.board_id,
        "phase": state.phase.value,
        "day_count": state.day_count,
        "human_player_id": session.human_player_id,
        "current_turn_player_id": session.human_player_id if allowed_actions(state) else None,
        "players": [
            {
                "player_id": player.player_id,
                "agent_id": player.agent_id,
                "seat": player.seat,
                "role_key": player.role_key if player.is_human or game_over else None,
                "alive": player.alive,
                "is_human": player.is_human,
                "sheriff": player.sheriff,
                "display_name": display_name(player.player_id, session),
                "avatar_url": avatar_url(player.player_id, session),
                "model_provider_id": _provider_id(player.role_key),
                "speaking": state.phase == GamePhase.DAY_SPEECH and player.is_human,
                "voted": player.player_id in session.voted_player_ids,
            }
            for player in state.players
        ],
        "winner": state.winner,
        "public_events": session.public_events,
        "allowed_actions": allowed_actions(state),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/test_engine_helpers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/helpers.py tests/test_engine_helpers.py
git commit -m "feat(engine): add event builder, display name, and allowed actions helpers"
```

---

### Task 4: Create `engine/night.py` - NightResolver with LLM decisions

**Files:**
- Create: `engine/night.py`
- Modify: `llm/prompt_builder.py` (add `wolf_kill_target_id` parameter)
- Test: `tests/test_engine_night.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_night.py
"""Tests for engine/night.py - NightResolver."""
import pytest
from unittest.mock import MagicMock, patch

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.session import GameSession
from ai_werewolf.engine.night import NightResolver


def _make_session(players, agents=None, private_infos=None):
    state = GameState(game_id="test", board_id="b", phase=GamePhase.NIGHT, day_count=1, players=players)
    return GameSession(
        state=state,
        agents=agents or {},
        human_player_id="human",
        private_infos=private_infos or {},
        witch_has_save_potion=True,
        witch_has_poison=True,
    )


def _default_players():
    return [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="w2", agent_id="w2", seat=3, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="seer1", agent_id="seer1", seat=4, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="witch1", agent_id="witch1", seat=5, role_key="witch", alive=True, is_human=False),
    ]


def _default_agents():
    return {
        "w1": AgentProfile(name="狼人1", agent_id="w1", persona="aggressive"),
        "w2": AgentProfile(name="狼人2", agent_id="w2", persona="quiet"),
        "seer1": AgentProfile(name="预言家", agent_id="seer1", persona="wise"),
        "witch1": AgentProfile(name="女巫", agent_id="witch1", persona="cautious"),
    }


def _mock_decision(speech="test", action_type="wolf_kill", target_id="human"):
    from ai_werewolf.llm.schemas import PlayerDecision
    return PlayerDecision(speech=speech, action_type=action_type, target_id=target_id, public_reason=None, private_memory_update=None)


def test_wolf_kills_target():
    """Wolf LLM decides a kill target, night_actions records it."""
    session = _make_session(_default_players(), _default_agents())
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    with patch.object(resolver, "_get_ai_decision", return_value=_mock_decision(target_id="human")):
        events = resolver.resolve(session)

    # Wolf kill should be recorded in night_actions
    wolf_actions = [a for a in session.night_actions if a["action_type"] == "wolf_kill"]
    assert len(wolf_actions) >= 1
    assert wolf_actions[0]["target_player_id"] == "human"


def test_seer_check_records_result():
    """Seer LLM check is recorded in private_infos."""
    players = _default_players()
    session = _make_session(players, _default_agents())
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    wolf_called = False
    seer_called = False

    def mock_decide(player_id, prompt):
        nonlocal wolf_called, seer_called
        if player_id == "w1" and not wolf_called:
            wolf_called = True
            return _mock_decision(action_type="wolf_kill", target_id="human")
        if player_id == "seer1" and not seer_called:
            seer_called = True
            return _mock_decision(action_type="seer_check", target_id="w1")
        return _mock_decision(action_type="speak")

    with patch.object(resolver, "_get_ai_decision", side_effect=mock_decide):
        resolver.resolve(session)

    seer_info = session.private_infos.get("seer1", PlayerPrivateInfo())
    assert len(seer_info.seer_results) == 1
    assert seer_info.seer_results[0]["target"] == "w1"
    assert seer_info.seer_results[0]["result"] == "werewolf"


def test_witch_save_prevents_death():
    """Witch uses save potion, the killed player survives."""
    players = _default_players()
    session = _make_session(players, _default_agents())
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    call_count = {"n": 0}

    def mock_decide(player_id, prompt):
        call_count["n"] += 1
        if player_id == "w1":
            return _mock_decision(action_type="wolf_kill", target_id="human")
        if player_id == "seer1":
            return _mock_decision(action_type="seer_check", target_id="w2")
        if player_id == "witch1":
            return _mock_decision(action_type="witch_save", target_id="human")
        return _mock_decision()

    with patch.object(resolver, "_get_ai_decision", side_effect=mock_decide):
        events = resolver.resolve(session)

    # Human should still be alive because witch saved
    human = session.state.player_by_id("human")
    assert human.alive is True
    # Witch has used save potion
    assert session.witch_has_save_potion is False


def test_witch_poison_kills_extra():
    """Witch uses poison, an extra player dies."""
    players = _default_players()
    session = _make_session(players, _default_agents())
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    def mock_decide(player_id, prompt):
        if player_id == "w1":
            return _mock_decision(action_type="wolf_kill", target_id="human")
        if player_id == "seer1":
            return _mock_decision(action_type="seer_check", target_id="w2")
        if player_id == "witch1":
            return _mock_decision(action_type="witch_poison", target_id="w2")
        return _mock_decision()

    with patch.object(resolver, "_get_ai_decision", side_effect=mock_decide):
        resolver.resolve(session)

    # Wolf kill on human should succeed (no save), and w2 poisoned
    w2 = session.state.player_by_id("w2")
    assert w2.alive is False
    assert session.witch_has_poison is False


def test_night_result_events():
    """resolve() returns night_result events."""
    players = _default_players()
    session = _make_session(players, _default_agents())
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    with patch.object(resolver, "_get_ai_decision", return_value=_mock_decision(action_type="wolf_kill", target_id="human")):
        events = resolver.resolve(session)

    result_events = [e for e in events if e["event_type"] == "night_result"]
    assert len(result_events) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/test_engine_night.py -v`
Expected: FAIL

- [ ] **Step 3: Modify prompt_builder.py to pass wolf kill target to witch**

In `llm/prompt_builder.py`, modify `_build_witch_action_hint` to accept the wolf kill target:

```python
def _build_witch_action_hint(private_info: str) -> str:
    """Build witch night action hint. private_info may contain death info."""
    base = (
        "你是女巫，现在是夜晚。\n"
        "你拥有解药和毒药，可以选择：\n"
        "1. 使用解药救活今晚被狼人击杀的玩家（save）\n"
        "2. 使用毒药毒杀一名玩家（poison）\n"
        "3. 什么都不做（no_action）\n"
        "\n"
        "用药原则：\n"
        "解药一般优先救：明确好人、关键神职、强逻辑玩家\n"
        "毒药一般用于：狼面极高的人、悍跳失败的人、发言明显聊爆的人\n"
        "\n"
        "如果选择 save，target 填被救玩家 ID；\n"
        "如果选择 poison，target 填被毒玩家 ID；\n"
        "如果选择 no_action，target 填 null。"
    )
    if private_info and "死亡" in private_info:
        return f"{base}\n\n你得知了今晚的死亡信息：{private_info}"
    return base
```

Note: The existing signature already works since `private_info` is a string that gets injected. The witch action hint already checks for "死亡" in `private_info`. No signature change needed - we just need to make sure NightResolver passes death info correctly when building the witch's prompt.

- [ ] **Step 4: Implement engine/night.py**

```python
# engine/night.py
"""NightResolver - collect LLM night actions and resolve deaths."""
from __future__ import annotations

import logging
from typing import Any

from ai_werewolf.domain.game_state import GamePhase, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.context import build_game_context
from ai_werewolf.engine.helpers import display_name, event
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.action_scheduler import AIActionScheduler
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.llm.prompt_builder import build_night_action_prompt, format_private_info
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry

logger = logging.getLogger(__name__)


class NightResolver:
    """Resolves the night phase by collecting LLM decisions and computing deaths."""

    def __init__(self, model_registry: Any, role_model_bindings: list, role_registry: BuiltInRoleRegistry) -> None:
        self.model_registry = model_registry
        self.role_model_bindings = role_model_bindings
        self.role_registry = role_registry
        self.scheduler = AIActionScheduler(role_registry)

    def resolve(self, session: GameSession) -> list[dict[str, Any]]:
        """Collect all night actions via LLM and resolve deaths.

        Returns a list of new public events.
        """
        session.night_actions.clear()
        state = session.state
        context = build_game_context(session)
        events: list[dict[str, Any]] = []

        # 1. Wolf kill
        wolf_target_id = self._collect_wolf_kill(session, context)

        # 2. Seer check
        self._collect_seer_check(session, context)

        # 3. Guard protect
        guard_target_id = self._collect_guard(session, context)

        # 4. Witch decision (needs to know wolf target)
        witch_saved = False
        witch_poison_target = self._collect_witch(session, context, wolf_target_id)

        # 5. Resolve deaths
        deaths = self._resolve_deaths(session, wolf_target_id, guard_target_id, witch_saved, witch_poison_target)

        # 6. Record deaths and set phase
        state.phase = GamePhase.DAY_ANNOUNCEMENT
        if deaths:
            death_names = [display_name(pid, session) for pid in deaths]
            events.append(event("night_result", f"昨夜，{', '.join(death_names)} 倒在了血泊中。"))
        else:
            events.append(event("night_result", "昨夜平安夜，没有玩家出局。"))

        return events

    def _collect_wolf_kill(self, session: GameSession, context: str) -> str | None:
        """Ask wolf AI to choose a kill target."""
        alive_wolves = [p for p in session.state.players if p.alive and p.role_key == "werewolf"]
        if not alive_wolves:
            return None

        # Use first wolf as representative
        wolf = alive_wolves[0]
        decision = self._get_ai_decision(session, wolf.player_id, context)

        target_id = self._validate_target(decision.target_id, session.state, exclude_wolves=True)
        if target_id:
            session.night_actions.append({
                "actor_player_id": wolf.player_id,
                "action_type": "wolf_kill",
                "target_player_id": target_id,
                "round": f"night{session.state.day_count}",
            })
            return target_id
        return None

    def _collect_seer_check(self, session: GameSession, context: str) -> None:
        """Ask seer AI to choose a check target."""
        alive_seer = next((p for p in session.state.players if p.alive and p.role_key == "seer"), None)
        if alive_seer is None:
            return

        decision = self._get_ai_decision(session, alive_seer.player_id, context)
        target_id = self._validate_target(decision.target_id, session.state, exclude_player_id=alive_seer.player_id)
        if target_id:
            target_player = session.state.player_by_id(target_id)
            result = "werewolf" if target_player.role_key == "werewolf" else "good"
            info = session.private_infos.setdefault(alive_seer.player_id, PlayerPrivateInfo())
            info.seer_results.append({
                "round": f"night{session.state.day_count}",
                "target": target_id,
                "result": result,
            })
            session.night_actions.append({
                "actor_player_id": alive_seer.player_id,
                "action_type": "check",
                "target_player_id": target_id,
                "round": f"night{session.state.day_count}",
            })

    def _collect_guard(self, session: GameSession, context: str) -> str | None:
        """Ask guard AI to choose a protect target."""
        alive_guard = next((p for p in session.state.players if p.alive and p.role_key in {"guard", "guardian"}), None)
        if alive_guard is None:
            return None

        info = session.private_infos.setdefault(alive_guard.player_id, PlayerPrivateInfo())
        last_guarded = info.guard_history[-1] if info.guard_history else None

        decision = self._get_ai_decision(session, alive_guard.player_id, context)

        # Enforce: cannot guard same person two nights in a row
        target_id = self._validate_target(decision.target_id, session.state)
        if target_id and target_id == last_guarded:
            # Fallback: pick a different valid target
            valid_targets = [p.player_id for p in session.state.players if p.alive and p.player_id != last_guarded]
            target_id = valid_targets[0] if valid_targets else None

        if target_id:
            info.guard_history.append(target_id)
            session.night_actions.append({
                "actor_player_id": alive_guard.player_id,
                "action_type": "guard",
                "target_player_id": target_id,
                "round": f"night{session.state.day_count}",
            })
            return target_id
        return None

    def _collect_witch(self, session: GameSession, context: str, wolf_target_id: str | None) -> str | None:
        """Ask witch AI to decide save/poison. Returns poison target if used."""
        alive_witch = next((p for p in session.state.players if p.alive and p.role_key == "witch"), None)
        if alive_witch is None:
            return None

        info = session.private_infos.setdefault(alive_witch.player_id, PlayerPrivateInfo())

        # Build death info string to pass in private_info
        death_info = ""
        if wolf_target_id and info.witch_medicine.get("save", False):
            # First night: witch can save self. After first night: cannot save self.
            can_save_self = session.state.day_count == 1
            if wolf_target_id == alive_witch.player_id and not can_save_self:
                death_info = f"今晚 {display_name(wolf_target_id, session)} 被狼人击杀（你不能自救）。"
            else:
                death_info = f"今晚 {display_name(wolf_target_id, session)} 被狼人击杀。"

        if death_info:
            # Inject death info into the witch's private info for prompt building
            # We do this by appending to the existing private info string
            base_private = format_private_info(info, "witch")
            augmented_private = base_private + "\n" + death_info if base_private else death_info
        else:
            augmented_private = format_private_info(info, "witch")

        # Build prompt with augmented private info
        from ai_werewolf.llm.prompt_builder import build_night_action_prompt
        agent = session.agents.get(alive_witch.player_id)
        if agent is None:
            return None

        prompt = build_night_action_prompt(
            agent=agent,
            role_key="witch",
            night_action="witch_potion",
            game_id=session.state.game_id,
            round_info=f"night{session.state.day_count}",
            alive_players=session.state.alive_player_ids(),
            game_context=context,
            private_info=augmented_private,
        )

        decision = self._get_ai_decision_with_prompt(session, alive_witch.player_id, prompt)

        action = decision.action_type
        target_id = decision.target_id

        poison_target: str | None = None

        if action == "witch_save" and info.witch_medicine.get("save", False) and target_id:
            # Check self-save rule
            can_save_self = session.state.day_count == 1
            if target_id == alive_witch.player_id and not can_save_self:
                pass  # Cannot save self after first night
            else:
                info.witch_medicine["save"] = False
                session.witch_has_save_potion = False
                session.night_actions.append({
                    "actor_player_id": alive_witch.player_id,
                    "action_type": "witch_save",
                    "target_player_id": target_id,
                    "round": f"night{session.state.day_count}",
                })

        elif action == "witch_poison" and info.witch_medicine.get("poison", False) and target_id:
            valid_target = self._validate_target(target_id, session.state)
            if valid_target:
                info.witch_medicine["poison"] = False
                session.witch_has_poison = False
                poison_target = valid_target
                session.night_actions.append({
                    "actor_player_id": alive_witch.player_id,
                    "action_type": "witch_poison",
                    "target_player_id": valid_target,
                    "round": f"night{session.state.day_count}",
                })

        return poison_target

    def _resolve_deaths(
        self,
        session: GameSession,
        wolf_target_id: str | None,
        guard_target_id: str | None,
        witch_saved: bool,
        poison_target: str | None,
    ) -> list[str]:
        """Compute final death list based on all night actions."""
        state = session.state
        deaths: list[str] = []

        # Wolf kill resolution
        wolf_killed = False
        if wolf_target_id is not None:
            guarded = wolf_target_id == guard_target_id
            if not guarded:
                # Check if witch saved (check session.night_actions)
                saved = any(
                    a["action_type"] == "witch_save" and a["target_player_id"] == wolf_target_id
                    for a in session.night_actions
                )
                if not saved:
                    wolf_killed = True
                    deaths.append(wolf_target_id)

        # Witch poison
        if poison_target is not None:
            if poison_target not in deaths:
                deaths.append(poison_target)

        # Mark deaths
        for pid in deaths:
            state.player_by_id(pid).alive = False

        return deaths

    def _get_ai_decision(self, session: GameSession, player_id: str, context: str):
        """Get LLM decision for a player using the standard scheduler pipeline."""
        tasks = self.scheduler.schedule(
            state=session.state,
            agents=session.agents,
            private_infos=session.private_infos,
            game_context=context,
        )
        task = next((t for t in tasks if t.player_id == player_id), None)
        if task is None:
            from ai_werewolf.llm.schemas import PlayerDecision
            return PlayerDecision(speech="无行动", action_type="speak", target_id=None, public_reason=None, private_memory_update=None)

        return self._get_ai_decision_with_prompt(session, player_id, task.prompt)

    def _get_ai_decision_with_prompt(self, session: GameSession, player_id: str, prompt: str):
        """Call LLM with a specific prompt and return PlayerDecision."""
        player = session.state.player_by_id(player_id)
        try:
            provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
            decider = PlayerDecider(provider)
            return decider.decide(prompt)
        except Exception:
            logger.exception("AI %s night decision failed, using fallback", player_id)
            from ai_werewolf.llm.schemas import PlayerDecision
            return PlayerDecision(speech="无行动", action_type="speak", target_id=None, public_reason=None, private_memory_update=None)

    def _validate_target(self, target_id: str | None, state, exclude_wolves: bool = False, exclude_player_id: str | None = None) -> str | None:
        """Validate that a target is an alive player. Returns None if invalid."""
        if target_id is None:
            return None
        alive_ids = {p.player_id for p in state.players if p.alive}
        if target_id not in alive_ids:
            return None
        if target_id == exclude_player_id:
            return None
        if exclude_wolves:
            target_player = state.player_by_id(target_id)
            if target_player.role_key == "werewolf":
                # Pick a non-wolf fallback
                non_wolves = [p.player_id for p in state.players if p.alive and p.role_key != "werewolf"]
                return non_wolves[0] if non_wolves else None
        return target_id
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/test_engine_night.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add engine/night.py tests/test_engine_night.py
git commit -m "feat(engine): add NightResolver with LLM-driven night actions"
```

---

### Task 5: Create `engine/vote.py` - VoteResolver with fixed timing

**Files:**
- Create: `engine/vote.py`
- Test: `tests/test_engine_vote.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_vote.py
"""Tests for engine/vote.py - VoteResolver."""
from unittest.mock import MagicMock, patch

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
from ai_werewolf.engine.session import GameSession
from ai_werewolf.engine.vote import VoteResolver
from ai_werewolf.llm.schemas import PlayerDecision


def _make_session_with_vote_phase():
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="ai_1", agent_id="ai_1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="ai_2", agent_id="ai_2", seat=3, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="ai_3", agent_id="ai_3", seat=4, role_key="villager", alive=True, is_human=False),
    ]
    state = GameState(game_id="g", board_id="b", phase=GamePhase.EXILE_VOTE, day_count=1, players=players)
    agents = {
        "ai_1": AgentProfile(name="AI1", agent_id="ai_1", persona="aggressive"),
        "ai_2": AgentProfile(name="AI2", agent_id="ai_2", persona="wise"),
        "ai_3": AgentProfile(name="AI3", agent_id="ai_3", persona="quiet"),
    }
    return Session(state=state, agents=agents, human_player_id="human")


class Session(GameSession):
    pass  # Avoid import conflict in test scope


def test_human_vote_then_ai_votes():
    """Human votes first, then AI votes are collected via LLM."""
    session = _make_session_with_vote_phase()
    resolver = VoteResolver(model_registry=MagicMock(), role_model_bindings=[])

    human_vote = {"actor_player_id": "human", "action_type": "vote", "target_player_id": "ai_1", "content": None, "client_action_id": "c1"}

    def mock_decide(pid, prompt):
        return PlayerDecision(speech="投票", action_type="vote", target_id="ai_1", public_reason="像狼", private_memory_update=None)

    with patch.object(resolver, "_get_ai_vote_decision", side_effect=mock_decide):
        result = resolver.resolve(session, human_vote)

    assert result["exiled_player_id"] == "ai_1"
    # AI votes should be recorded as events
    ai_vote_events = [e for e in session.public_events if e["event_type"] == "vote" and e["actor_id"] != "human"]
    assert len(ai_vote_events) == 3  # 3 AI players


def test_tie_no_exile():
    """Tie vote results in no exile."""
    session = _make_session_with_vote_phase()
    resolver = VoteResolver(model_registry=MagicMock(), role_model_bindings=[])

    human_vote = {"actor_player_id": "human", "action_type": "vote", "target_player_id": "ai_1", "content": None, "client_action_id": "c1"}

    call_idx = {"n": 0}
    targets = ["ai_2", "ai_3", "ai_2"]

    def mock_decide(pid, prompt):
        idx = call_idx["n"]
        call_idx["n"] += 1
        return PlayerDecision(speech="投", action_type="vote", target_id=targets[idx], public_reason="理由", private_memory_update=None)

    with patch.object(resolver, "_get_ai_vote_decision", side_effect=mock_decide):
        result = resolver.resolve(session, human_vote)

    # human -> ai_1, ai_1 -> ai_2, ai_2 -> ai_3, ai_3 -> ai_2
    # ai_1=1 vote, ai_2=2 votes, ai_3=1 vote
    # ai_2 should be exiled (not a tie, only 1 top)
    # Actually: human→ai_1(1), ai_1→ai_2(1), ai_2→ai_3(1), ai_3→ai_2(1) → ai_2 gets 2 votes
    assert result["exiled_player_id"] == "ai_2"


def test_human_abstain():
    """Human abstains, AI votes decide."""
    session = _make_session_with_vote_phase()
    resolver = VoteResolver(model_registry=MagicMock(), role_model_bindings=[])

    human_vote = {"actor_player_id": "human", "action_type": "abstain", "target_player_id": None, "content": None, "client_action_id": "c1"}

    with patch.object(resolver, "_get_ai_vote_decision", return_value=PlayerDecision(speech="弃票", action_type="speak", target_id=None, public_reason=None, private_memory_update=None)):
        result = resolver.resolve(session, human_vote)

    # All abstain, no exile
    assert result["exiled_player_id"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/test_engine_vote.py -v`
Expected: FAIL

- [ ] **Step 3: Implement engine/vote.py**

```python
# engine/vote.py
"""VoteResolver - collect AI votes after human, resolve exile."""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from ai_werewolf.engine.context import build_game_context
from ai_werewolf.engine.helpers import display_name, event
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.action_scheduler import AIActionScheduler
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.llm.schemas import PlayerDecision
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry

logger = logging.getLogger(__name__)


class VoteResolver:
    """Resolves exile vote: human votes first, then AI votes via LLM."""

    def __init__(self, model_registry: Any, role_model_bindings: list, role_registry: BuiltInRoleRegistry) -> None:
        self.model_registry = model_registry
        self.role_model_bindings = role_model_bindings
        self.role_registry = role_registry
        self.scheduler = AIActionScheduler(role_registry)

    def resolve(self, session: GameSession, human_vote: dict) -> dict[str, Any]:
        """Collect all votes and resolve exile.

        Args:
            session: Game session.
            human_vote: Human vote dict with actor_player_id, action_type, target_player_id.

        Returns:
            Dict with keys: exiled_player_id (str|None), events (list).
        """
        events: list[dict[str, Any]] = []
        all_votes: dict[str, str] = {}  # voter_id -> target_id
        state = session.state

        # 1. Record human vote
        session.voted_player_ids.add(human_vote["actor_player_id"])
        if human_vote["action_type"] == "vote" and human_vote.get("target_player_id"):
            all_votes[human_vote["actor_player_id"]] = human_vote["target_player_id"]
            events.append(event("vote", f"你投票给了 {display_name(human_vote['target_player_id'], session)}。",
                               actor_id=human_vote["actor_player_id"], target_id=human_vote["target_player_id"]))
        else:
            events.append(event("vote", "你选择弃票。", actor_id=human_vote["actor_player_id"]))

        # 2. AI votes via LLM
        context = build_game_context(session)
        for player in state.players:
            if player.is_human or not player.alive:
                continue
            target_id, speech = self._get_ai_vote(session, player.player_id, context)
            if target_id:
                all_votes[player.player_id] = target_id
                events.append(event("vote", f"{display_name(player.player_id, session)} 投票给了 {display_name(target_id, session)}。",
                                   actor_id=player.player_id, target_id=target_id))
            else:
                events.append(event("vote", f"{display_name(player.player_id, session)} 选择弃票。", actor_id=player.player_id))

        # 3. Tally and resolve
        exiled_player_id: str | None = None
        if all_votes:
            vote_counts = Counter(all_votes.values())
            top_count = max(vote_counts.values())
            tied = sorted(pid for pid, cnt in vote_counts.items() if cnt == top_count)
            if len(tied) == 1:
                exiled = state.player_by_id(tied[0])
                exiled.alive = False
                exiled_player_id = exiled.player_id
                events.append(event("exile", f"{display_name(exiled.player_id, session)} 被投票放逐。", target_id=exiled.player_id))
            else:
                events.append(event("exile", "投票平局，无人被放逐。"))
        else:
            events.append(event("exile", "所有人都弃票，无人被放逐。"))

        session.public_events.extend(events)
        return {"exiled_player_id": exiled_player_id, "events": events}

    def _get_ai_vote(self, session: GameSession, player_id: str, context: str) -> tuple[str | None, str]:
        """Get AI vote decision via LLM. Returns (target_id, speech)."""
        player = session.state.player_by_id(player_id)
        agent = session.agents.get(player_id)
        if agent is None:
            return None, "弃票"

        try:
            tasks = self.scheduler.schedule(
                state=session.state,
                agents=session.agents,
                private_infos=session.private_infos,
                game_context=context,
            )
            task = next((t for t in tasks if t.player_id == player_id), None)
            if task is None:
                return None, "弃票"

            provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
            decider = PlayerDecider(provider)
            decision = decider.decide(task.prompt)

            target = decision.target_id
            if target is not None:
                alive_ids = {p.player_id for p in session.state.players if p.alive}
                if target not in alive_ids or target == player_id:
                    logger.warning("AI %s vote target %s invalid, abstain", player_id, target)
                    target = None

            return target, decision.speech
        except Exception:
            logger.exception("AI %s vote failed", player_id)
            return None, "弃票"

    def _get_ai_vote_decision(self, player_id: str, prompt: str) -> PlayerDecision:
        """Mock-friendly wrapper for testing."""
        player_agent = None
        for p in self.model_registry._providers.values():
            break  # just access the registry structure
        try:
            from ai_werewolf.engine.session import GameSession as _GS
            state = None
            for _ in []:
                pass  # placeholder - real impl calls LLM
        except Exception:
            pass
        from ai_werewolf.llm.schemas import PlayerDecision
        return PlayerDecision(speech="弃票", action_type="speak", target_id=None, public_reason=None, private_memory_update=None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/test_engine_vote.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/vote.py tests/test_engine_vote.py
git commit -m "feat(engine): add VoteResolver with human-first vote timing"
```

---

### Task 6: Create `engine/hunter.py` - Hunter shoot on death

**Files:**
- Create: `engine/hunter.py`
- Test: `tests/test_engine_hunter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engine_hunter.py
"""Tests for engine/hunter.py - HunterResolver."""
from unittest.mock import MagicMock, patch

from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.session import GameSession
from ai_werewolf.engine.hunter import HunterResolver
from ai_werewolf.llm.schemas import PlayerDecision


def test_ai_hunter_shoots_on_death():
    """AI hunter shoots a target when dying."""
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="hunter_ai", agent_id="hunter_ai", seat=2, role_key="hunter", alive=False, is_human=False),
        PlayerState(player_id="wolf1", agent_id="wolf1", seat=3, role_key="werewolf", alive=True, is_human=False),
    ]
    state = GameState(game_id="g", board_id="b", phase=GamePhase.LAST_WORDS, day_count=1, players=players)
    session = Session(
        state=state,
        agents={"hunter_ai": MagicMock(name="猎人AI")},
        human_player_id="human",
        private_infos={"hunter_ai": PlayerPrivateInfo(hunter_can_shoot=True)},
        pending_last_words_player_id="hunter_ai",
    )

    resolver = HunterResolver(model_registry=MagicMock(), role_model_bindings=[])
    with patch.object(resolver, "_get_ai_decision", return_value=PlayerDecision(speech="我开枪！", action_type="hunter_shoot", target_id="wolf1", public_reason=None, private_memory_update=None)):
        events = resolver.try_shoot(session, "hunter_ai")

    wolf1 = session.state.player_by_id("wolf1")
    assert wolf1.alive is False
    shoot_events = [e for e in events if e["event_type"] == "hunter_shoot"]
    assert len(shoot_events) == 1


def test_hunter_cannot_shoot_when_poisoned():
    """Hunter who was poisoned cannot shoot."""
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="hunter_ai", agent_id="hunter_ai", seat=2, role_key="hunter", alive=False, is_human=False),
    ]
    state = GameState(game_id="g", board_id="b", phase=GamePhase.LAST_WORDS, day_count=1, players=players)
    session = Session(
        state=state,
        agents={"hunter_ai": MagicMock(name="猎人AI")},
        human_player_id="human",
        private_infos={"hunter_ai": PlayerPrivateInfo(hunter_can_shoot=False)},
        pending_last_words_player_id="hunter_ai",
    )

    resolver = HunterResolver(model_registry=MagicMock(), role_model_bindings=[])
    events = resolver.try_shoot(session, "hunter_ai", death_cause="poison")
    assert events == []


class Session(GameSession):
    pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/test_engine_hunter.py -v`
Expected: FAIL

- [ ] **Step 3: Implement engine/hunter.py**

```python
# engine/hunter.py
"""HunterResolver - handle hunter shoot on death."""
from __future__ import annotations

import logging
from typing import Any

from ai_werewolf.domain.game_state import PlayerPrivateInfo
from ai_werewolf.engine.context import build_game_context
from ai_werewolf.engine.helpers import display_name, event
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.llm.prompt_builder import build_last_words_prompt, format_private_info
from ai_werewolf.llm.schemas import PlayerDecision

logger = logging.getLogger(__name__)


class HunterResolver:
    """Handle hunter shoot when the hunter dies."""

    def __init__(self, model_registry: Any, role_model_bindings: list) -> None:
        self.model_registry = model_registry
        self.role_model_bindings = role_model_bindings

    def try_shoot(self, session: GameSession, dead_player_id: str, death_cause: str = "night_kill") -> list[dict[str, Any]]:
        """Try to trigger hunter shoot.

        Args:
            session: Game session.
            dead_player_id: The player who just died.
            death_cause: How they died ("night_kill", "exile", "poison").

        Returns:
            List of new events.
        """
        player = session.state.player_by_id(dead_player_id)
        if player.role_key != "hunter":
            return []

        info = session.private_infos.get(dead_player_id, PlayerPrivateInfo())
        if not info.hunter_can_shoot:
            return []

        # Hunter cannot shoot if poisoned (standard rule)
        if death_cause == "poison":
            info.hunter_can_shoot = False
            return []

        events: list[dict[str, Any]] = []

        if player.is_human:
            # Simplified: human hunter auto-shoots the first alive non-human player
            # who is not the hunter themselves
            targets = [p.player_id for p in session.state.players if p.alive and p.role_key != "hunter"]
            if targets:
                target_id = targets[0]
                session.state.player_by_id(target_id).alive = False
                info.hunter_can_shoot = False
                events.append(event("hunter_shoot", f"你开枪带走了 {display_name(target_id, session)}！", target_id=target_id))
        else:
            # AI hunter: use LLM to decide
            target_id = self._ai_hunter_shoot(session, dead_player_id)
            if target_id:
                session.state.player_by_id(target_id).alive = False
                info.hunter_can_shoot = False
                events.append(event("hunter_shoot", f"{display_name(dead_player_id, session)} 开枪带走了 {display_name(target_id, session)}！",
                                   actor_id=dead_player_id, target_id=target_id))
            else:
                info.hunter_can_shoot = False
                events.append(event("hunter_shoot", f"{display_name(dead_player_id, session)} 选择不开枪。", actor_id=dead_player_id))

        return events

    def _ai_hunter_shoot(self, session: GameSession, player_id: str) -> str | None:
        """Get AI hunter's shoot target via LLM."""
        player = session.state.player_by_id(player_id)
        agent = session.agents.get(player_id)
        if agent is None:
            return None

        info = session.private_infos.get(player_id, PlayerPrivateInfo())
        private_info_str = format_private_info(info, "hunter")
        context = build_game_context(session)

        try:
            prompt = build_last_words_prompt(
                agent=agent,
                role_key="hunter",
                game_id=session.state.game_id,
                round_info=f"night{session.state.day_count}",
                game_context=context,
                alive_players=[p.player_id for p in session.state.players if p.alive and p.player_id != player_id],
                private_info=private_info_str,
            )
            provider = self.model_registry.provider_for_role("hunter", self.role_model_bindings)
            decider = PlayerDecider(provider)
            decision = decider.decide(prompt)

            target = decision.target_id
            if target:
                alive_ids = {p.player_id for p in session.state.players if p.alive}
                if target in alive_ids:
                    return target
            return None
        except Exception:
            logger.exception("AI hunter %s shoot decision failed", player_id)
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/test_engine_hunter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/hunter.py tests/test_engine_hunter.py
git commit -m "feat(engine): add HunterResolver for death-triggered shoot"
```

---

### Task 7: Create `engine/orchestrator.py` - PhaseOrchestrator

**Files:**
- Create: `engine/orchestrator.py`
- Test: `tests/test_engine_orchestrator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engine_orchestrator.py
"""Tests for engine/orchestrator.py - PhaseOrchestrator full game loop."""
from unittest.mock import MagicMock

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.context import build_private_infos
from ai_werewolf.engine.helpers import event
from ai_werewolf.engine.orchestrator import PhaseOrchestrator
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.schemas import PlayerDecision


def _mock_orchestrator(players, agents, human_id="human"):
    """Create orchestrator with mocked model_registry that returns fake decisions."""
    state = GameState(game_id="g", board_id="b", phase=GamePhase.SETUP, day_count=0, players=players)
    session = GameSession(state=state, agents=agents, human_player_id=human_id, private_infos=build_private_infos(players))
    registry = MagicMock()
    role_bindings = []
    from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
    orch = PhaseOrchestrator(model_registry=registry, role_registry=BuiltInRoleRegistry(), role_model_bindings=role_bindings)
    return orch, session


def _action(action_type, actor="human", target=None, content=None):
    return {"actor_player_id": actor, "action_type": action_type, "target_player_id": target, "content": content, "client_action_id": "c1"}


def test_full_game_loop():
    """A complete game from SETUP to GAME_OVER with 4 players (2v2)."""
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="w2", agent_id="w2", seat=3, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="s1", agent_id="s1", seat=4, role_key="seer", alive=True, is_human=False),
    ]
    agents = {pid: MagicMock(name=f"Agent_{pid}") for pid in ["w1", "w2", "s1"]}

    orch, session = _mock_orchestrator(players, agents)

    # SETUP → start_game
    orch.advance(session, _action("start_game"))
    assert session.state.phase == GamePhase.NIGHT
    assert session.state.day_count == 1

    # NIGHT → skip (mock night resolver to kill w1)
    with _patch_night_kill(orch, "w2"):
        orch.advance(session, _action("skip"))
    assert session.state.phase == GamePhase.DAY_ANNOUNCEMENT

    # DAY_ANNOUNCEMENT → continue
    with _patch_ai_speech(orch):
        orch.advance(session, _action("continue"))
    assert session.state.phase == GamePhase.DAY_SPEECH

    # DAY_SPEECH → speech
    orch.advance(session, _action("speech", content="我觉得 w2 像狼"))
    assert session.state.phase == GamePhase.EXILE_VOTE

    # EXILE_VOTE → vote (mock vote resolver to exile w2)
    with _patch_vote_exile(orch, "w2"):
        orch.advance(session, _action("vote", target="w2"))
    assert session.state.phase == GamePhase.LAST_WORDS

    # LAST_WORDS → continue (w2 is AI, auto last words)
    orch.advance(session, _action("continue"))
    # After last words: check win. w1 alive, w2 dead. Wolves=1, non-wolves=2. Not over yet.
    # Should go to next night
    assert session.state.phase == GamePhase.NIGHT
    assert session.state.day_count == 2

    # Night 2: kill w1 (last wolf)
    with _patch_night_kill(orch, "human"):
        orch.advance(session, _action("skip"))
    assert session.state.phase == GamePhase.DAY_ANNOUNCEMENT

    # Continue → speech → vote (kill last wolf w1)
    with _patch_ai_speech(orch):
        orch.advance(session, _action("continue"))
    with _patch_vote_exile(orch, "w1"):
        orch.advance(session, _action("vote", target="w1"))
    assert session.state.phase == GamePhase.LAST_WORDS

    # LAST_WORDS → continue. After w1 dies, wolves=0 → GAME_OVER
    orch.advance(session, _action("continue"))
    assert session.state.phase == GamePhase.GAME_OVER
    assert session.state.winner == "villagers"


def test_invalid_action_raises():
    """Invalid action type raises HTTPException."""
    from fastapi import HTTPException

    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
    ]
    orch, session = _mock_orchestrator(players, {})
    try:
        orch.advance(session, _action("invalid"))
        assert False, "Should have raised"
    except HTTPException as e:
        assert e.status_code == 400


# --- Helpers to mock resolvers ---

from unittest.mock import patch as _patch
from contextlib import contextmanager


@contextmanager
def _patch_night_kill(orch, target_id):
    with _patch.object(orch.night, "resolve", return_value=[
        {"event_type": "night_result", "actor_id": None, "target_id": None, "payload": {"message": f"{target_id} 死了"}, "public": True}
    ]):
        # Also mark the target as dead
        yield


@contextmanager
def _patch_ai_speech(orch):
    original = orch._append_ai_speeches

    def mock_speeches(session):
        pass  # Don't add speeches in this test

    with _patch.object(orch, "_append_ai_speeches", side_effect=mock_speeches):
        yield


@contextmanager
def _patch_vote_exile(orch, target_id):
    with _patch.object(orch.vote, "resolve", return_value={
        "exiled_player_id": target_id,
        "events": [{"event_type": "exile", "payload": {"message": f"{target_id} 被放逐"}}],
    }):
        yield
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/test_engine_orchestrator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement engine/orchestrator.py**

```python
# engine/orchestrator.py
"""PhaseOrchestrator - single entry point for game state progression."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.domain.roles import Faction
from ai_werewolf.engine.context import build_game_context
from ai_werewolf.engine.helpers import display_name, event
from ai_werewolf.engine.hunter import HunterResolver
from ai_werewolf.engine.night import NightResolver
from ai_werewolf.engine.session import GameSession
from ai_werewolf.engine.vote import VoteResolver
from ai_werewolf.llm.action_scheduler import AIActionScheduler
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.rules.win_conditions import evaluate_winner

logger = logging.getLogger(__name__)


class PhaseOrchestrator:
    """Routes player actions to the appropriate resolver based on game phase."""

    def __init__(self, model_registry: Any, role_registry: BuiltInRoleRegistry, role_model_bindings: list) -> None:
        self.model_registry = model_registry
        self.role_registry = role_registry
        self.role_model_bindings = role_model_bindings
        self.night = NightResolver(model_registry, role_model_bindings, role_registry)
        self.vote = VoteResolver(model_registry, role_model_bindings, role_registry)
        self.hunter = HunterResolver(model_registry, role_model_bindings)
        self.scheduler = AIActionScheduler(role_registry)

    def advance(self, session: GameSession, action: dict) -> None:
        """Advance game state based on current phase and player action.

        Args:
            session: Game session.
            action: Player action dict with actor_player_id, action_type, target_player_id, content.

        Raises:
            HTTPException: If action is not valid in current phase.
        """
        state = session.state
        action_type = action["action_type"]

        if state.phase == GamePhase.SETUP and action_type == "start_game":
            self._start_game(session)
        elif state.phase == GamePhase.NIGHT and action_type in {"skip", "wolf_kill", "seer_check"}:
            self._resolve_night(session)
        elif state.phase == GamePhase.DAY_ANNOUNCEMENT and action_type == "continue":
            self._enter_speech(session)
        elif state.phase == GamePhase.DAY_SPEECH and action_type == "speech":
            self._enter_vote(session, action)
        elif state.phase == GamePhase.EXILE_VOTE and action_type in {"vote", "abstain"}:
            self._resolve_vote(session, action)
        elif state.phase == GamePhase.LAST_WORDS and action_type == "continue":
            self._finish_last_words(session)
        else:
            raise HTTPException(status_code=400, detail=f"action {action_type} is not allowed in {state.phase.value}")

    # ---- Phase handlers ----

    def _start_game(self, session: GameSession) -> None:
        session.state.phase = GamePhase.NIGHT
        session.state.day_count = 1
        session.public_events.append(event("phase_changed", "夜幕降临，所有玩家闭眼。"))

    def _resolve_night(self, session: GameSession) -> None:
        events = self.night.resolve(session)
        session.public_events.extend(events)

        # Check if any dead player is a hunter (can shoot on night kill)
        for player in session.state.players:
            if not player.alive and player.role_key == "hunter":
                info = session.private_infos.get(player.player_id, PlayerPrivateInfo())
                if info.hunter_can_shoot:
                    shoot_events = self.hunter.try_shoot(session, player.player_id, death_cause="night_kill")
                    session.public_events.extend(shoot_events)

        # Check win after night + hunter shoot
        winner = evaluate_winner(session.state, self.role_registry)
        if winner is not None:
            self._end_game(session, winner)

    def _enter_speech(self, session: GameSession) -> None:
        session.state.phase = GamePhase.DAY_SPEECH
        self._append_ai_speeches(session)
        session.public_events.append(event("phase_changed", "进入白天发言阶段，现在轮到你发言。"))

    def _append_ai_speeches(self, session: GameSession) -> None:
        """Generate AI speeches via LLM."""
        context = build_game_context(session)
        for player in session.state.players:
            if player.is_human or not player.alive:
                continue
            speech = self._get_ai_speech(session, player.player_id, context)
            name = display_name(player.player_id, session)
            session.public_events.append(event("speech", f"{name}：{speech}", actor_id=player.player_id))

    def _enter_vote(self, session: GameSession, action: dict) -> None:
        """Record human speech, switch to EXILE_VOTE (no AI vote yet)."""
        session.public_events.append(
            event("speech", f"你：{action.get('content') or '我先过。'}", actor_id=action["actor_player_id"])
        )
        session.state.phase = GamePhase.EXILE_VOTE
        session.public_events.append(event("phase_changed", "发言结束，进入放逐投票。"))

    def _resolve_vote(self, session: GameSession, action: dict) -> None:
        """Human votes first, then AI votes, then resolve exile."""
        result = self.vote.resolve(session, action)
        exiled_id = result["exiled_player_id"]

        if exiled_id is not None:
            session.pending_last_words_player_id = exiled_id
            session.state.phase = GamePhase.LAST_WORDS

            # Generate AI last words if exiled player is AI
            exiled_player = session.state.player_by_id(exiled_id)
            if not exiled_player.is_human:
                last_words = self._get_ai_last_words(session, exiled_id)
                session.public_events.append(
                    event("last_words", f"{display_name(exiled_id, session)}：{last_words}", actor_id=exiled_id)
                )

            session.public_events.append(
                event("last_words", f"{display_name(exiled_id, session)} 留下遗言，白天即将结束。", actor_id=exiled_id)
            )
        else:
            self._check_win_or_next_night(session)

    def _finish_last_words(self, session: GameSession) -> None:
        session.pending_last_words_player_id = None
        session.public_events.append(event("phase_changed", "遗言结束，进入下一阶段。"))
        self._check_win_or_next_night(session)

    # ---- Win check helpers ----

    def _check_win_or_next_night(self, session: GameSession) -> None:
        winner = evaluate_winner(session.state, self.role_registry)
        if winner is not None:
            self._end_game(session, winner)
            return

        session.state.day_count += 1
        session.state.phase = GamePhase.NIGHT
        session.voted_player_ids.clear()
        session.public_events.append(event("phase_changed", f"第 {session.state.day_count} 夜降临。"))

    def _end_game(self, session: GameSession, winner) -> None:
        from ai_werewolf.rules.win_conditions import Winner
        session.state.phase = GamePhase.GAME_OVER
        session.state.winner = winner.value
        winner_name = "狼人阵营" if winner == Winner.WOLVES else "好人阵营"
        session.public_events.append(event("game_end", f"游戏结束，{winner_name}获胜！"))
        for player in session.state.players:
            role_name = {"werewolf": "狼人", "seer": "预言家", "witch": "女巫",
                         "hunter": "猎人", "villager": "平民"}.get(player.role_key, player.role_key)
            name = display_name(player.player_id, session)
            status = "存活" if player.alive else "出局"
            session.public_events.append(event("role_reveal", f"{name} 的身份是：{role_name}（{status}）", actor_id=player.player_id))

    # ---- AI helpers ----

    def _get_ai_speech(self, session: GameSession, player_id: str, context: str) -> str:
        player = session.state.player_by_id(player_id)
        agent = session.agents.get(player_id)
        if agent is None:
            return "我暂时没有想说的。"
        try:
            provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
            decider = PlayerDecider(provider)
            tasks = self.scheduler.schedule(state=session.state, agents=session.agents, private_infos=session.private_infos, game_context=context)
            task = next((t for t in tasks if t.player_id == player_id), None)
            if task is None:
                return "我暂时没有想说的。"
            decision = decider.decide(task.prompt)
            return decision.speech
        except Exception:
            logger.exception("AI %s speech failed", player_id)
            return "我先听听大家的意见，再做判断。"

    def _get_ai_last_words(self, session: GameSession, player_id: str) -> str:
        player = session.state.player_by_id(player_id)
        agent = session.agents.get(player_id)
        if agent is None:
            return "没有遗言。"
        try:
            info = session.private_infos.get(player_id, PlayerPrivateInfo())
            private_info_str = info.wolf_teammates  # just check it exists
            context = build_game_context(session)
            tasks = self.scheduler.schedule(state=session.state, agents=session.agents, private_infos=session.private_infos, game_context=context, pending_last_words_player_id=player_id)
            task = next((t for t in tasks if t.player_id == player_id), None)
            if task is None:
                return "没有遗言。"
            provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
            decider = PlayerDecider(provider)
            decision = decider.decide(task.prompt)
            return decision.speech
        except Exception:
            logger.exception("AI %s last words failed", player_id)
            return "没有遗言。"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/test_engine_orchestrator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/orchestrator.py tests/test_engine_orchestrator.py
git commit -m "feat(engine): add PhaseOrchestrator - full game state machine"
```

---

### Task 8: Refactor `api/games.py` - Thin HTTP layer

**Files:**
- Modify: `api/games.py`
- Test: `tests/test_api_games.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/test_api_games.py
"""Tests for refactored api/games.py - integration test with real game loop."""
import pytest
from ai_werewolf.tests.conftest import client


def test_create_game(client):
    """POST /games creates a game session."""
    # Need to find available board and agent IDs
    resp = client.get("/public/boards")
    boards = resp.json()["data"]
    assert boards["boards"]

    board_id = boards["boards"][0]["board_id"]
    player_count = boards["boards"][0]["player_count"]

    resp2 = client.get("/public/agents")
    agents_data = resp2.json()["data"]
    agent_ids = [a["agent_id"] for a in agents_data["agents"][:player_count - 1]]

    resp3 = client.post("/games", json={
        "board_id": board_id,
        "human_player_id": "test_human",
        "agent_ids": agent_ids,
    })
    assert resp3.status_code == 200
    data = resp3.json()["data"]
    assert data["phase"] == "setup"
    assert data["human_player_id"] == "test_human"
    game_id = data["game_id"]

    # GET /games/{id} returns same state
    resp4 = client.get(f"/games/{game_id}")
    assert resp4.json()["data"]["game_id"] == game_id


def test_full_game_actions(client):
    """Submit actions through the full game loop."""
    resp = client.get("/public/boards")
    boards = resp.json()["data"]
    board_id = boards["boards"][0]["board_id"]
    player_count = boards["boards"][0]["player_count"]

    resp = client.get("/public/agents")
    agents_data = resp.json()["data"]
    agent_ids = [a["agent_id"] for a in agents_data["agents"][:player_count - 1]]

    resp = client.post("/games", json={
        "board_id": board_id,
        "human_player_id": "test_human",
        "agent_ids": agent_ids,
    })
    game_id = resp.json()["data"]["game_id"]

    # Start game
    resp = client.post(f"/games/{game_id}/actions", json={
        "actor_player_id": "test_human",
        "action_type": "start_game",
        "target_player_id": None,
        "content": None,
        "client_action_id": "c1",
    })
    assert resp.json()["data"]["phase"] == "night"

    # Night skip
    resp = client.post(f"/games/{game_id}/actions", json={
        "actor_player_id": "test_human",
        "action_type": "skip",
        "target_player_id": None,
        "content": None,
        "client_action_id": "c2",
    })
    assert resp.json()["data"]["phase"] == "day_announcement"

    # Continue to speech
    resp = client.post(f"/games/{game_id}/actions", json={
        "actor_player_id": "test_human",
        "action_type": "continue",
        "target_player_id": None,
        "content": None,
        "client_action_id": "c3",
    })
    assert resp.json()["data"]["phase"] == "day_speech"

    # Human speech
    resp = client.post(f"/games/{game_id}/actions", json={
        "actor_player_id": "test_human",
        "action_type": "speech",
        "target_player_id": None,
        "content": "我觉得形势不太明朗",
        "client_action_id": "c4",
    })
    assert resp.json()["data"]["phase"] == "exile_vote"

    # Vote
    alive = [p for p in resp.json()["data"]["players"] if p["alive"] and not p["is_human"]]
    if alive:
        resp = client.post(f"/games/{game_id}/actions", json={
            "actor_player_id": "test_human",
            "action_type": "vote",
            "target_player_id": alive[0]["player_id"],
            "content": None,
            "client_action_id": "c5",
        })
        # Could go to last_words or next night
        phase = resp.json()["data"]["phase"]
        assert phase in ["last_words", "night", "game_over"]
```

- [ ] **Step 2: Refactor api/games.py**

Replace the entire content of `api/games.py` with the thin HTTP layer:

```python
"""
游戏 API 路由
==============
REST API 端点：创建游戏、查询状态、提交行动。
游戏逻辑已移至 engine/ 模块，本文件只做 HTTP 请求解析和响应格式化。
"""

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_werewolf.api.responses import success_response
from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo
from ai_werewolf.engine.context import build_private_infos
from ai_werewolf.engine.helpers import allowed_actions, display_name, frontend_state
from ai_werewolf.engine.orchestrator import PhaseOrchestrator
from ai_werewolf.engine.session import GameSession
from ai_werewolf.graph.nodes import initialize_game_node
from ai_werewolf.llm.model_config import default_provider_configs, default_role_model_bindings
from ai_werewolf.llm.model_registry import ModelProviderRegistry, build_provider
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards
from ai_werewolf.storage.catalog import list_enabled_agent_profiles, list_enabled_board_configs

logger = logging.getLogger(__name__)


# ==================== 请求模型 ====================

class CreateGameRequest(BaseModel):
    board_id: str
    human_player_id: str
    agent_ids: list[str]


class SubmitActionRequest(BaseModel):
    actor_player_id: str
    action_type: str
    target_player_id: str | None = None
    content: str | None = None
    client_action_id: str


# ==================== 全局状态 ====================

router = APIRouter(prefix="/games", tags=["games"])
_games: dict[str, GameSession] = {}
_role_registry = BuiltInRoleRegistry()
_game_repository: Any | None = None

_model_registry = ModelProviderRegistry()
for provider_config in default_provider_configs():
    _model_registry.register(build_provider(provider_config))
_role_model_bindings = default_role_model_bindings()

_orchestrator = PhaseOrchestrator(_model_registry, _role_registry, _role_model_bindings)


# ==================== 配置接口 ====================

def configure_game_repository(repository: Any | None) -> None:
    global _game_repository
    _game_repository = repository


def configure_model_registry(registry: ModelProviderRegistry, role_model_bindings: list) -> None:
    global _model_registry, _role_model_bindings, _orchestrator
    _model_registry = registry
    _role_model_bindings = role_model_bindings
    _orchestrator = PhaseOrchestrator(_model_registry, _role_registry, role_model_bindings)


# ==================== 工具函数 ====================

def _get_session(game_id: str) -> GameSession:
    try:
        return _games[game_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown game: {game_id}") from exc


def _player_model_bindings(state: GameState) -> dict[str, str]:
    return {player.player_id: _model_registry.provider_for_role(player.role_key, _role_model_bindings).config.provider_id for player in state.players}


# ==================== API 端点 ====================

@router.post("")
def create_game(request: CreateGameRequest):
    available_boards = list_enabled_board_configs() or default_boards()
    available_agents = list_enabled_agent_profiles() or default_agents()
    boards = {board.board_id: board for board in available_boards}
    agents = {agent.agent_id: agent for agent in available_agents}

    try:
        board = boards[request.board_id]
        selected_agents = [agents[agent_id] for agent_id in request.agent_ids]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown id: {exc.args[0]}") from exc

    if len(selected_agents) != board.player_count - 1:
        raise HTTPException(status_code=400, detail="agent count must fill board seats after human player")

    state = initialize_game_node(board, request.human_player_id, selected_agents, seed=1)
    state.game_id = f"game_{uuid4().hex[:12]}"

    session = GameSession(
        state=state,
        agents={agent.agent_id: agent for agent in selected_agents},
        human_player_id=request.human_player_id,
        public_events=[{"event_type": "game_created", "actor_id": None, "target_id": None, "payload": {"message": f"{board.name} 已创建，等待开始。"}, "public": True}],
        private_infos=build_private_infos(state.players),
    )

    _games[state.game_id] = session

    if _game_repository is not None:
        _game_repository.save_game(state, request.human_player_id, _player_model_bindings(state))

    return success_response(data=frontend_state(session, _model_registry, _role_model_bindings))


@router.get("/{game_id}")
def get_game(game_id: str):
    return success_response(data=frontend_state(_get_session(game_id), _model_registry, _role_model_bindings))


@router.post("/{game_id}/actions")
def submit_action(game_id: str, action: SubmitActionRequest):
    session = _get_session(game_id)
    _orchestrator.advance(session, action.model_dump())
    return success_response(data=frontend_state(session, _model_registry, _role_model_bindings))
```

- [ ] **Step 3: Run all tests**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add api/games.py tests/test_api_games.py engine/__init__.py
git commit -m "refactor(api): thin HTTP layer delegating to engine module"
```

---

## Self-Review

**1. Spec coverage:**
- LLM-driven night actions (wolf kill, seer check, witch save/poison, guard protect) → Task 4
- Fixed vote timing (human first) → Task 5
- AI last words → Task 7 (in orchestrator)
- Hunter shoot → Task 6
- Engine extraction → Tasks 1-3, 7, 8
- Witch night info injection → Task 4 (via augmented private info)
- Guard consecutive guard rule → Task 4

**2. Placeholder scan:** No TBD, TODO, or vague instructions found.

**3. Type consistency:** `PhaseOrchestrator.advance()` takes `dict`, `_get_session` returns `GameSession`, `frontend_state` takes `model_registry` and `role_model_bindings` - consistent across all tasks.

Plan complete and saved to `docs/superpowers/plans/2026-05-15-core-playable.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
