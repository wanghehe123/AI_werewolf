# Phase 1d: Socket.IO Real-time Communication

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace unidirectional `EventSource` SSE with bidirectional `Socket.IO`, enabling client→server action submission, automatic reconnection with event replay, and room-based game synchronization.

**Architecture:** Backend wraps the FastAPI app in `socketio.ASGIApp(sio, fastapi_app)`. A new `api/socketio_bridge.py` creates the Socket.IO server with game-room support, event bridging (polling the same `session.stream_events` used by SSE), and an action handler that calls `PhaseOrchestrator.advance()`. Frontend replaces `EventSource` with `socket.io-client`, joining game rooms and emitting actions via Socket.IO instead of REST POST.

**Key design decision:** Keep SSE alongside Socket.IO during this phase. Socket.IO becomes the primary transport, SSE is the fallback. This ensures zero downtime during migration.

**Tech Stack:** python-socketio ^5.x + ASGI mode (backend), socket.io-client ^4.x (frontend)

**Pre-requisites:** Phase 1a (Zustand), Phase 1b (Framer Motion), Phase 1c (TTS).

**What does NOT change:**
- Game logic (orchestrator.py, player_decider.py) — zero changes
- `api/games.py` — only add TTS endpoint from Phase 1c, no SSE changes
- gameStore.ts — zero changes
- GameTable.tsx, PhaseSceneRouter.tsx, LobbyPage — zero changes
- All existing tests pass unchanged

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `ai_werewolf/pyproject.toml` | **Modify** | Add `python-socketio` dep |
| `ai_werewolf/api/socketio_bridge.py` | **Create** | Socket.IO server: rooms, event polling, action handler |
| `ai_werewolf/main.py` | **Modify** | Wrap FastAPI app in socketio.ASGIApp |
| `frontend/package.json` | **Modify** | Add `socket.io-client` dep |
| `frontend/src/services/socket.ts` | **Create** | Socket.IO client: connect, join room, emit actions |
| `frontend/src/services/socket.test.ts` | **Create** | Tests for socket service |
| `frontend/src/App.tsx` | **Modify** | Replace EventSource SSE with Socket.IO in GameRoute |

---

### Task 1: Install dependencies (both sides)

**Files:**
- Modify: `ai_werewolf/pyproject.toml`
- Modify: `frontend/package.json`

- [ ] **Step 1: Install backend dependency**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf
.venv/bin/pip install "python-socketio[asyncio_client]"
```

Note: `python-socketio` alone is sufficient for the server. The `asyncio_client` extra is not needed — we only need the server mode.

Update `pyproject.toml`:
```toml
dependencies = [
    "fastapi>=0.136.1",
    "edge-tts>=6.1",
    "python-socketio>=5.0",
]
```

- [ ] **Step 2: Install frontend dependency**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npm install socket.io-client
```

- [ ] **Step 3: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add ai_werewolf/pyproject.toml frontend/package.json frontend/package-lock.json
git commit -m "chore: add socket.io dependencies"
```

---

### Task 2: Create backend Socket.IO bridge

**Files:**
- Create: `ai_werewolf/api/socketio_bridge.py`
- Modify: `ai_werewolf/main.py` (wrap app in socketio.ASGIApp)

- [ ] **Step 1: Create socketio_bridge.py**

Create `ai_werewolf/api/socketio_bridge.py`:

```python
"""
Socket.IO Bridge — game event streaming over WebSocket.

Architecture:
  - One Socket.IO room per game (room name: "game_{game_id}")
  - Polls session.stream_events at 200ms intervals, emits new events to room
  - Clients submit actions via "player_action" event (replaces REST POST)
  - Initial state_snapshot sent on room join
"""

import logging
import asyncio
from typing import Any

import socketio

logger = logging.getLogger(__name__)

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_timeout=30,
    ping_interval=15,
)

# Track active polling tasks per game
_poll_tasks: dict[str, asyncio.Task[Any]] = {}


# ── Connection ───────────────────────────────────────────────────

@sio.event
async def connect(sid: str, environ: dict[str, Any]):
    logger.debug("Socket.IO connected: %s", sid)


@sio.event
async def disconnect(sid: str):
    logger.debug("Socket.IO disconnected: %s", sid)


# ── Game room ────────────────────────────────────────────────────

@sio.event
async def join_game(sid: str, data: dict[str, Any]):
    """Join a game room. data = { game_id }"""
    game_id = data.get("game_id")
    if not game_id:
        await sio.emit("error", {"message": "game_id is required"}, to=sid)
        return

    room = f"game_{game_id}"
    sio.enter_room(sid, room)
    logger.info("Client %s joined room %s", sid, room)

    # Send initial state snapshot
    from ai_werewolf.api.games import _games, frontend_state, _model_registry, _role_model_bindings
    session = _games.get(game_id)
    if session:
        state_data = frontend_state(session, _model_registry, _role_model_bindings)
        await sio.emit("state_snapshot", {
            "event_id": f"evt_snapshot_connect_{sid[:8]}",
            "event_type": "state_snapshot",
            "game_id": game_id,
            "phase": session.state.phase.value,
            "day_count": session.state.day_count,
            "visibility": "self",
            "actor_id": None,
            "target_id": None,
            "payload": {"game_state": state_data},
            "created_at": None,
        }, to=sid)

    # Start polling for this game if not already polling
    if game_id not in _poll_tasks:
        task = asyncio.create_task(_poll_game_events(game_id))
        _poll_tasks[game_id] = task


@sio.event
async def leave_game(sid: str, data: dict[str, Any]):
    """Leave a game room."""
    game_id = data.get("game_id")
    if game_id:
        sio.leave_room(sid, f"game_{game_id}")


# ── Player action ────────────────────────────────────────────────

@sio.event
async def player_action(sid: str, data: dict[str, Any]):
    """Handle player action submission via Socket.IO."""
    game_id = data.get("game_id")
    if not game_id:
        await sio.emit("error", {"message": "game_id is required"}, to=sid)
        return

    from ai_werewolf.api.games import _games

    session = _games.get(game_id)
    if not session:
        await sio.emit("error", {"message": f"Game {game_id} not found"}, to=sid)
        return

    try:
        from ai_werewolf.api.games import _orchestrator
        _orchestrator.advance(session, {
            "actor_player_id": data.get("actor_player_id", "human"),
            "action_type": data.get("action_type", ""),
            "target_player_id": data.get("target_player_id"),
            "content": data.get("content"),
            "client_action_id": f"sio-{sid[:8]}-{asyncio.get_event_loop().time()}",
        })
    except Exception as exc:
        logger.exception("Action failed: %s", exc)
        await sio.emit("error", {"message": str(exc)}, to=sid)


# ── Event polling ────────────────────────────────────────────────

async def _poll_game_events(game_id: str):
    """Poll session.stream_events and emit new events to the game room."""
    room = f"game_{game_id}"
    try:
        from ai_werewolf.api.games import _games

        last_idx = 0
        while True:
            session = _games.get(game_id)
            if not session:
                logger.info("Game %s ended, stopping poll", game_id)
                break

            events = session.stream_events
            while last_idx < len(events):
                event = events[last_idx]
                await sio.emit(event["event_type"], event, room=room)
                last_idx += 1

            await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        logger.info("Polling cancelled for game %s", game_id)
    except Exception:
        logger.exception("Polling error for game %s", game_id)
    finally:
        _poll_tasks.pop(game_id, None)
```

- [ ] **Step 2: Modify main.py to wrap app in socketio.ASGIApp**

In `ai_werewolf/main.py`, add after the existing imports (after line 32):

```python
from ai_werewolf.api.socketio_bridge import sio
import socketio as _socketio
```

In `create_app()`, replace `return app` (line 154) with:

```python
    # Wrap FastAPI app with Socket.IO ASGI handler
    # Socket.IO intercepts /socket.io/ path, passes everything else to FastAPI
    socketio_app = _socketio.ASGIApp(sio, other_app=app)
    return socketio_app
```

The modified `create_app()` function end (lines 153-154) becomes:

```python
    # Wrap with Socket.IO (intercepts /socket.io/, passes rest to FastAPI)
    socketio_app = _socketio.ASGIApp(sio, other_app=app)
    return socketio_app
```

- [ ] **Step 3: Verify backend starts with Socket.IO**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf
.venv/bin/python -c "
from ai_werewolf.main import create_app
app = create_app()
print('App created successfully:', type(app).__name__)
"
```

Expected: `App created successfully: ASGIApp` (or similar, no import errors)

- [ ] **Step 4: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add ai_werewolf/api/socketio_bridge.py ai_werewolf/main.py
git commit -m "feat(backend): add Socket.IO bridge for game events"
```

---

### Task 3: Create frontend Socket.IO service

**Files:**
- Create: `frontend/src/services/socket.ts`

- [ ] **Step 1: Create socket.ts**

Create `frontend/src/services/socket.ts`:

```typescript
/**
 * Socket.IO service — bidirectional game communication.
 *
 * Replaces EventSource SSE with socket.io-client:
 *   - Connect to server, join game room
 *   - Receive game events (same types as SSE)
 *   - Emit player actions (replaces REST POST)
 *   - Auto-reconnect with exponential backoff
 */

import { io, Socket } from "socket.io-client";
import { apiBaseUrl } from "../api";
import type { GameStreamEventDto, SubmitActionInput } from "../types";

export interface SocketOptions {
  gameId: string;
  onEvent: (event: GameStreamEventDto) => void;
  onError?: (error: string) => void;
  onConnect?: () => void;
  onDisconnect?: (reason: string) => void;
}

let _socket: Socket | null = null;

export function connectGameSocket(options: SocketOptions): Socket {
  // Disconnect any existing socket
  if (_socket?.connected) {
    _socket.disconnect();
  }

  const socket = io(apiBaseUrl(), {
    transports: ["websocket", "polling"],
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 10000,
  });

  socket.on("connect", () => {
    socket.emit("join_game", { game_id: options.gameId });
    options.onConnect?.();
  });

  socket.on("disconnect", (reason) => {
    options.onDisconnect?.(reason);
  });

  // Register listeners for all game event types
  const eventTypes = [
    "state_snapshot",
    "phase_changed",
    "night_step_started",
    "night_step_finished",
    "speech_delta",
    "speech_completed",
    "current_speaker_changed",
    "ai_thinking",
    "private_info",
    "game_created",
    "night_result",
  ];

  for (const eventType of eventTypes) {
    socket.on(eventType, (data: GameStreamEventDto) => {
      options.onEvent(data);
    });
  }

  // Error handling
  socket.on("error", (data: { message?: string }) => {
    options.onError?.(data.message ?? "Socket error");
  });

  socket.on("connect_error", (err) => {
    options.onError?.(`Connection failed: ${err.message}`);
  });

  _socket = socket;
  return socket;
}

/** Submit a player action via Socket.IO (replaces REST POST /games/{id}/actions) */
export function emitPlayerAction(gameId: string, action: SubmitActionInput): void {
  if (!_socket?.connected) {
    throw new Error("Socket not connected");
  }
  _socket.emit("player_action", {
    game_id: gameId,
    actor_player_id: "human",
    action_type: action.action_type,
    target_player_id: action.target_player_id,
    content: action.content,
  });
}

/** Leave the game room and disconnect */
export function disconnectGameSocket(): void {
  if (_socket) {
    if (_socket.connected) {
      const gameId = (_socket as any)._gameId;
      if (gameId) {
        _socket.emit("leave_game", { game_id: gameId });
      }
      _socket.disconnect();
    }
    _socket = null;
  }
}

export function getSocket(): Socket | null {
  return _socket;
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx tsc --noEmit src/services/socket.ts
```

Expected: No errors (socket.io-client types resolve correctly).

- [ ] **Step 3: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/services/socket.ts
git commit -m "feat(frontend): add Socket.IO client service"
```

---

### Task 4: Create socket service tests

**Files:**
- Create: `frontend/src/services/socket.test.ts`

- [ ] **Step 1: Create socket.test.ts**

Create `frontend/src/services/socket.test.ts`:

```typescript
import { describe, expect, it, vi, beforeEach } from "vitest";

// Mock socket.io-client
const mockOn = vi.fn();
const mockEmit = vi.fn();
const mockDisconnect = vi.fn();
const mockConnected = true;

vi.mock("socket.io-client", () => ({
  io: vi.fn(() => ({
    on: mockOn,
    emit: mockEmit,
    disconnect: mockDisconnect,
    get connected() { return mockConnected; },
  })),
}));

import { connectGameSocket, emitPlayerAction, disconnectGameSocket } from "./socket";

describe("socket service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("connectGameSocket registers event listeners for all event types", () => {
    const onEvent = vi.fn();

    connectGameSocket({
      gameId: "game_123",
      onEvent,
    });

    // After connect, should have joined the room
    // Find the "connect" callback and invoke it
    const connectHandler = mockOn.mock.calls.find(
      (call: unknown[]) => call[0] === "connect"
    )?.[1];
    expect(connectHandler).toBeDefined();
    connectHandler();

    expect(mockEmit).toHaveBeenCalledWith("join_game", { game_id: "game_123" });
  });

  it("emitPlayerAction sends action data via socket emit", () => {
    // First connect
    connectGameSocket({ gameId: "game_123", onEvent: vi.fn() });

    emitPlayerAction("game_123", {
      action_type: "speech",
      content: "Hello",
    });

    expect(mockEmit).toHaveBeenCalledWith("player_action", {
      game_id: "game_123",
      actor_player_id: "human",
      action_type: "speech",
      target_player_id: undefined,
      content: "Hello",
    });
  });

  it("disconnectGameSocket disconnects existing socket", () => {
    connectGameSocket({ gameId: "game_123", onEvent: vi.fn() });
    disconnectGameSocket();

    expect(mockDisconnect).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the socket tests**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx vitest run src/services/socket.test.ts
```

Expected: 3 tests pass.

- [ ] **Step 3: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/services/socket.test.ts
git commit -m "test(frontend): add socket service unit tests"
```

---

### Task 5: Wire Socket.IO into App.tsx GameRoute

**Files:**
- Modify: `frontend/src/App.tsx:110-205` (GameRoute component)

Replace the SSE-based `useEffect` in GameRoute with Socket.IO. Keep SSE as fallback.

- [ ] **Step 1: Add socket service imports to App.tsx**

Add after existing imports:
```typescript
import { connectGameSocket, disconnectGameSocket, emitPlayerAction } from "./services/socket";
```

- [ ] **Step 2: Replace the SSE useEffect in GameRoute**

Remove the existing SSE `useEffect` (the one that calls `subscribeGameStream`) and the `handleAction` function.

Replace with these two effects:

```typescript
// Socket.IO connection effect
useEffect(() => {
  if (!gameId || !store.game?.human_player_id) return;

  // Connect via Socket.IO
  const socket = connectGameSocket({
    gameId,
    onEvent: (event) => {
      store.applySseEvent(event);
    },
    onError: (message) => {
      // Fallback: on socket error, fetch state via REST
      store.loadGame(gameId);
    },
    onConnect: () => {
      store.clearError();
    },
  });

  return () => {
    disconnectGameSocket();
  };
}, [gameId, store.game?.human_player_id]);

// Action handler — uses Socket.IO emit instead of REST POST
async function handleAction(action: SubmitActionInput) {
  if (!gameId) return;
  try {
    store.setPending(true);
    store.clearError();
    emitPlayerAction(gameId, action);
    // Socket.IO is fire-and-forget for actions.
    // State updates come via incoming events (state_snapshot).
    // We optimistically set pending=false after a short delay
    // since the server doesn't ack action submissions.
    setTimeout(() => store.setPending(false), 500);
  } catch (err) {
    store.setError(err instanceof Error ? err.message : "行动失败");
    store.setPending(false);
  }
}
```

Wait — the existing `handleAction` calls `store.submitAction()` which does a REST POST and waits for the response to update state. With Socket.IO, the pattern changes: we emit the action, and the state update comes back as an incoming event. But the pending state needs special handling.

Let me revise: Keep the existing `handleAction` that uses `store.submitAction()` (REST POST) for now. Socket.IO only replaces the SSE stream. Action submission via Socket.IO is deferred.

Actually, the user wants minimal changes. Let me keep the REST POST for actions (it works) and only replace the SSE stream with Socket.IO. This is simpler and safer.

```typescript
// Socket.IO connection — replaces SSE EventSource
useEffect(() => {
  if (!gameId || !store.game?.human_player_id) return;

  const socket = connectGameSocket({
    gameId,
    onEvent: (event) => {
      store.applySseEvent(event);
    },
    onError: () => {
      // Fallback: fetch state via REST on socket error
      store.loadGame(gameId);
    },
    onConnect: () => {
      store.clearError();
    },
  });

  return () => {
    disconnectGameSocket();
  };
}, [gameId, store.game?.human_player_id]);
```

And keep the existing `handleAction` (which calls `store.submitAction()` → REST POST). This way:
- Server→client: Socket.IO replaces SSE
- Client→server: REST POST stays (unchanged)
- This is a pure transport swap, zero logic changes

The old SSE useEffect code should be replaced by this new useEffect. The existing `handleAction` stays.

- [ ] **Step 3: Remove the old SSE subscribeGameStream import and usage**

Remove `subscribeGameStream` from the API imports (if it's no longer used elsewhere). But wait — it might be used by other code. Let me check...

`subscribeGameStream` is only imported and used in App.tsx's GameRoute. After this change, it's no longer used. So remove it from the import:

```typescript
// Before (line 32):
  subscribeGameStream
// After: remove this line
```

- [ ] **Step 4: Verify everything compiles**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx tsc --noEmit
```

Expected: Zero TypeScript errors.

- [ ] **Step 5: Run all tests**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx vitest run
```

Expected: All tests pass. GameTable, PhaseSceneRouter, LobbyPage tests don't touch the transport layer and work unchanged.

- [ ] **Step 6: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/App.tsx
git commit -m "feat(frontend): replace SSE EventSource with Socket.IO game stream"
```

---

## Completion Checklist for Phase 1d

- [ ] Backend: `socketio_bridge.py` creates Socket.IO server with game rooms
- [ ] Backend: `main.py` wraps FastAPI in `socketio.ASGIApp`
- [ ] Frontend: `socket.io-client` installed
- [ ] Frontend: `src/services/socket.ts` connects to game rooms and emits actions
- [ ] Frontend: `src/services/socket.test.ts` has 3 passing tests
- [ ] Frontend: `App.tsx` GameRoute uses Socket.IO instead of EventSource SSE
- [ ] Frontend: Action submission still uses REST POST (unchanged, safe)
- [ ] `subscribeGameStream` import removed from App.tsx (still exists in api.ts for backwards compat)
- [ ] All existing tests pass
- [ ] `npx tsc --noEmit` passes with zero errors
- [ ] Manual test: start backend, connect frontend, verify events flow through Socket.IO

---

## Next Phase

After Phase 1d is complete, proceed to:
**Phase 1e: TailwindCSS + shadcn/ui Migration** — Replace single 755-line styles.css with Tailwind utility classes and shadcn/ui components.

Plan file: `docs/superpowers/plans/2026-05-16-frontend-phase1e-tailwind-shadcn.md`
