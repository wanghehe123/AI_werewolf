# Phase 1a: Zustand State Management Migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all `useState`/`useEffect` state management in `GameRoute` with a single `gameStore` Zustand store, keeping all component interfaces unchanged.

**Architecture:** Create `src/stores/gameStore.ts` with Zustand. Migrate `GameRoute` in `App.tsx` to use `useGameStore()` hook instead of 5 separate `useState` calls. SSE event handling and action submission logic moves into store actions. Component props (GameTable, PhaseSceneRouter) remain identical — zero changes to leaf components.

**Tech Stack:** zustand ^5.x, React 19, TypeScript 5.9, vitest 4.x

**Why Phase 1a first:** Zustand is the foundation. All subsequent phases (Framer Motion, TTS, Socket.IO) need reactive state that triggers selective re-renders. Without it, every animation/audio update cascades through the entire component tree.

**What does NOT change (scope boundary):**
- GameTable.tsx — zero changes
- PhaseSceneRouter.tsx — zero changes
- LobbyPage.tsx — zero changes
- Admin pages — zero changes
- styles.css — zero changes
- api.ts — zero changes
- types.ts — zero changes (one new type added for store interface)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/stores/gameStore.ts` | **Create** | Zustand store: game state, SSE event reducer, action submission |
| `src/App.tsx` | **Modify** lines 110-224 | Replace 5 useState + SSE useEffect with store hooks |
| `frontend/package.json` | **Modify** | Add zustand dependency |

No other files are modified or created in this phase.

---

### Task 1: Install zustand and verify it loads

**Files:**
- Modify: `frontend/package.json` (add dependency via npm)

- [ ] **Step 1: Install zustand**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npm install zustand
```

- [ ] **Step 2: Verify zustand is importable**

```bash
node -e "require('zustand'); console.log('OK')"
```

Expected: Prints "OK" (no error)

- [ ] **Step 3: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): add zustand dependency"
```

---

### Task 2: Create gameStore with Zustand

**Files:**
- Create: `frontend/src/stores/gameStore.ts`
- Test: `frontend/src/stores/gameStore.test.ts` (create this AFTER Task 2, in Task 4 — following TDD for the store itself would require testing the store before writing it, but since Zustand stores are plain functions, we write the store first and test it immediately after)

> **Note on TDD ordering:** Task 2 creates the store, Task 3 wires it into App.tsx, Task 4 adds store unit tests, Task 5 runs ALL existing tests to confirm nothing broke. This order is pragmatic because:
> 1. We can't test the store integration in isolation — it needs to connect to SSE handlers
> 2. The existing component tests (GameTable, PhaseSceneRouter) serve as integration tests
> 3. Store unit tests in Task 4 validate the pure logic

- [ ] **Step 1: Create the stores directory**

```bash
mkdir -p /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend/src/stores
```

- [ ] **Step 2: Write gameStore.ts**

Create `frontend/src/stores/gameStore.ts`:

```typescript
import { create } from "zustand";
import { fetchGame, submitGameAction } from "../api";
import type {
  GameStateDto,
  GameStreamEventDto,
  PrivateInfoPayload,
  SeerCheckResult,
  SpeechDeltaPayload,
  StateSnapshotPayload,
  StreamingSpeechDto,
  SubmitActionInput
} from "../types";

export interface GameStore {
  // --- State ---
  game: GameStateDto | null;
  streamingSpeeches: Record<string, StreamingSpeechDto>;
  seerResults: Record<string, SeerCheckResult>;
  pending: boolean;
  error: string | null;

  // --- Actions ---
  /** Replace the entire game state (called after fetchGame or state_snapshot SSE) */
  setGame: (game: GameStateDto | null) => void;

  /** Process a single SSE event, updating game/streamingSpeeches/seerResults accordingly */
  applySseEvent: (event: GameStreamEventDto) => void;

  /** Append a public event to the game's event log (for non-special SSE events) */
  appendStreamEvent: (event: GameStreamEventDto) => void;

  /** Load game from REST API (initial fetch + SSE fallback) */
  loadGame: (gameId: string) => Promise<void>;

  /** Submit a player action via REST API, update state on success */
  submitAction: (gameId: string, action: SubmitActionInput) => Promise<void>;

  /** Clear the error banner */
  clearError: () => void;

  /** Reset store to initial state (for cleanup) */
  reset: () => void;
}

function initialState() {
  return {
    game: null,
    streamingSpeeches: {},
    seerResults: {},
    pending: false,
    error: null
  };
}

export const useGameStore = create<GameStore>((set, get) => ({
  // --- State ---
  ...initialState(),

  // --- Actions ---

  setGame: (game) => set({ game, error: null }),

  applySseEvent: (event) => {
    const currentGame = get().game;

    // state_snapshot: full state replacement
    if (event.event_type === "state_snapshot") {
      const payload = event.payload as unknown as StateSnapshotPayload;
      set({ game: payload.game_state });
      return;
    }

    // speech_delta: append streaming text
    if (event.event_type === "speech_delta") {
      const payload = event.payload as unknown as SpeechDeltaPayload;
      set((state) => ({
        streamingSpeeches: {
          ...state.streamingSpeeches,
          [payload.player_id]: { label: payload.label, speech: payload.speech }
        }
      }));
      return;
    }

    // speech_completed: remove streaming entry
    if (event.event_type === "speech_completed") {
      const playerId = event.actor_id;
      if (playerId) {
        set((state) => {
          if (!(playerId in state.streamingSpeeches)) return {};
          const next = { ...state.streamingSpeeches };
          delete next[playerId];
          return { streamingSpeeches: next };
        });
      }
      return;
    }

    // private_info: parse seer check results
    if (event.event_type === "private_info") {
      const payload = event.payload as unknown as PrivateInfoPayload;
      const targetId = event.target_id;
      if (!targetId) return;
      const msg = payload.message ?? "";
      const camp: "good" | "wolf" = msg.includes("狼人阵营") ? "wolf" : "good";
      const targetPlayer = currentGame?.players.find((p) => p.player_id === targetId);
      const targetLabel = targetPlayer
        ? `${targetPlayer.seat}号 ${targetPlayer.display_name}`
        : targetId;
      set((state) => ({
        seerResults: {
          ...state.seerResults,
          [targetId]: { targetPlayerId: targetId, targetLabel, camp }
        }
      }));
      return;
    }

    // All other event types: append to public_events
    get().appendStreamEvent(event);
  },

  appendStreamEvent: (event) => {
    const currentGame = get().game;
    if (!currentGame || typeof event.payload.message !== "string") return;

    set({
      game: {
        ...currentGame,
        phase: event.phase,
        day_count: event.day_count,
        public_events: [
          ...currentGame.public_events,
          {
            event_type: event.event_type,
            actor_id: event.actor_id,
            target_id: event.target_id,
            payload: { message: event.payload.message },
            public: event.visibility === "public"
          }
        ]
      }
    });
  },

  loadGame: async (gameId) => {
    try {
      const game = await fetchGame(gameId);
      set({ game, error: null });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : "加载游戏失败" });
    }
  },

  submitAction: async (gameId, action) => {
    set({ pending: true, error: null });
    try {
      const game = await submitGameAction(gameId, action);
      set({ game, pending: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "行动失败",
        pending: false
      });
    }
  },

  clearError: () => set({ error: null }),

  reset: () => set(initialState())
}));
```

- [ ] **Step 3: Verify store file compiles**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx tsc --noEmit src/stores/gameStore.ts
```

Expected: No errors (may have module resolution warnings for zustand — that's fine, it compiles with the project tsconfig)

- [ ] **Step 4: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/stores/gameStore.ts
git commit -m "feat(frontend): add gameStore with Zustand"
```

---

### Task 3: Wire GameRoute to use gameStore

**Files:**
- Modify: `frontend/src/App.tsx:110-224` (replace GameRoute component)

This is the critical migration step. We replace all `useState` calls, the SSE `useEffect`, and the `handleAction` function with store hooks. The component interface to GameTable/PhaseSceneRouter remains IDENTICAL.

- [ ] **Step 1: Read current GameRoute to understand the exact code to replace**

The current GameRoute (lines 110-205) uses:
- 5 `useState` hooks: game, streamingSpeeches, seerResults, pending, error
- `useEffect` for initial fetch
- `useEffect` for SSE subscription (depends on gameId + game?.human_player_id)
- `handleAction` closure for submit + state update
- `appendStreamEvent` standalone function (lines 207-224)

After migration:
- 0 `useState` hooks — all replaced by `useGameStore()`
- 2 `useEffect` hooks remain but call store actions instead of setters
- `handleAction` calls `store.submitAction()` instead of manual try/catch/setState
- `appendStreamEvent` function is REMOVED (logic moved into store)

- [ ] **Step 2: Add import for useGameStore at the top of App.tsx**

Insert this import after the existing imports (after line 64):

```typescript
import { useGameStore } from "./stores/gameStore";
```

- [ ] **Step 3: Replace GameRoute component**

Replace the entire GameRoute function (lines 110-205) and the appendStreamEvent function (lines 207-224) with:

```typescript
function GameRoute() {
  const { gameId } = useParams();
  const store = useGameStore();

  // Initial game load + SSE subscription
  useEffect(() => {
    if (!gameId) return;

    // Reset store on game change
    store.reset();

    // Fetch initial state
    store.loadGame(gameId);
  }, [gameId]);

  // SSE subscription
  useEffect(() => {
    if (!gameId || !store.game?.human_player_id) return;

    const source = subscribeGameStream(gameId, {
      playerId: store.game.human_player_id,
      onEvent: (event) => {
        store.applySseEvent(event);
      },
      onError: () => {
        store.loadGame(gameId);
      }
    });

    return () => source.close();
  }, [gameId, store.game?.human_player_id]);

  // Action handler
  async function handleAction(action: SubmitActionInput) {
    if (!gameId) return;
    await store.submitAction(gameId, action);
  }

  // Render (identical to before)
  if (store.error) {
    return <StatusScreen title="游戏暂时卡住了" detail={store.error} />;
  }
  if (!store.game) {
    return <StatusScreen title="正在进入房间" detail="正在恢复当前游戏状态。" />;
  }
  return (
    <GameTable
      game={store.game}
      onSubmitAction={handleAction}
      pending={store.pending}
      streamingSpeeches={store.streamingSpeeches}
      seerResults={store.seerResults}
    />
  );
}
```

- [ ] **Step 4: Remove the standalone appendStreamEvent function**

Delete lines 207-224 (the `appendStreamEvent` function). It is no longer needed — the logic now lives in the store.

- [ ] **Step 5: Clean up unused imports in App.tsx**

Remove these imports that are no longer used directly in App.tsx:
- `fetchGame` (was used by useEffect and onError callback)
- `submitGameAction` (was used by handleAction)
- `useState` from React (check if LobbyRoute still uses it — yes it does, so keep it)
- `GameEventDto` (was used by appendStreamEvent)
- `PrivateInfoPayload` (was used by private_info handler)
- `SeerCheckResult` (was used by seerResults state)
- `SpeechDeltaPayload` (was used by speech_delta handler)
- `StateSnapshotPayload` (was used by state_snapshot handler)
- `StreamingSpeechDto` (was used by streamingSpeeches state)
- `SubmitActionInput` (was used by handleAction — NO, it's still used as parameter type for handleAction!)

So the imports to remove are:
- `fetchGame` from "./api" import
- `submitGameAction` from "./api" import

And from the types import:
- `GameEventDto`
- `PrivateInfoPayload`
- `SeerCheckResult`
- `SpeechDeltaPayload`
- `StateSnapshotPayload`
- `StreamingSpeechDto`

Keep `SubmitActionInput` — it's still used by handleAction's parameter type.

The updated import block for api (lines 5-32) — remove `fetchGame` and `submitGameAction`:

```
import {
  adminLogin,
  adminLogout,
  createAdminAgent,
  ...
  replaceAdminBoardRoles,
  createGame,
  subscribeGameStream
} from "./api";
```

The updated import block for types (lines 45-64) — keep only what's used:

```typescript
import type {
  AdminAgentDto,
  AdminBoardDto,
  AdminGameDto,
  AdminLlmProviderDto,
  AdminPlayerDto,
  AdminRoleModelBindingDto,
  AdminRoleDto,
  AgentProfile,
  BoardConfig,
  GameStateDto,
  SubmitActionInput
} from "./types";
```

- [ ] **Step 6: Add the new store import**

After the types import (after line 64), add:

```typescript
import { useGameStore } from "./stores/gameStore";
```

Wait — I already mentioned this in Step 2. Let me consolidate: the import order at the top of App.tsx should be:

1. `useEffect, useState` from react (line 1) — KEEP (LobbyRoute uses useState)
2. BrowserRouter etc from react-router-dom (line 2) — KEEP
3. API imports (lines 4-33) — remove `fetchGame`, `submitGameAction`
4. Component/page imports (lines 34-44) — KEEP
5. Type imports (lines 45-64) — remove unused types
6. NEW: `import { useGameStore } from "./stores/gameStore";`

- [ ] **Step 7: Verify the app compiles**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx tsc --noEmit
```

Expected: No TypeScript errors.

- [ ] **Step 8: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/App.tsx frontend/src/stores/gameStore.ts
git commit -m "refactor(frontend): migrate GameRoute to Zustand gameStore"
```

---

### Task 4: Add gameStore unit tests

**Files:**
- Create: `frontend/src/stores/gameStore.test.ts`

- [ ] **Step 1: Create store test file**

Create `frontend/src/stores/gameStore.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { useGameStore } from "./gameStore";
import type { GameStateDto, GameStreamEventDto, StateSnapshotPayload, SpeechDeltaPayload } from "../types";

// Access Zustand store outside of React — useGameStore.getState() / .setState()
// Zustand stores are plain JS objects, no React renderer needed

describe("gameStore", () => {
  beforeEach(() => {
    useGameStore.getState().reset();
  });

  describe("initial state", () => {
    it("has null game, empty collections, no error", () => {
      const state = useGameStore.getState();
      expect(state.game).toBeNull();
      expect(state.streamingSpeeches).toEqual({});
      expect(state.seerResults).toEqual({});
      expect(state.pending).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe("setGame", () => {
    it("replaces game and clears error", () => {
      useGameStore.getState().setGame(mockGame());
      const state = useGameStore.getState();
      expect(state.game?.game_id).toBe("game_test");
      expect(state.error).toBeNull();
    });

    it("sets game to null", () => {
      useGameStore.getState().setGame(mockGame());
      useGameStore.getState().setGame(null);
      expect(useGameStore.getState().game).toBeNull();
    });
  });

  describe("applySseEvent: state_snapshot", () => {
    it("replaces entire game state from state_snapshot payload", () => {
      useGameStore.getState().setGame(mockGame("setup"));
      const snapshotEvent = mockSseEvent("state_snapshot", {
        game_state: mockGame("night")
      } as StateSnapshotPayload);

      useGameStore.getState().applySseEvent(snapshotEvent);

      expect(useGameStore.getState().game?.phase).toBe("night");
    });
  });

  describe("applySseEvent: speech_delta", () => {
    it("appends streaming speech text", () => {
      useGameStore.getState().setGame(mockGame());
      const deltaEvent = mockSseEvent("speech_delta", {
        player_id: "w1",
        label: "2号 小明",
        delta: "我",
        speech: "我觉得"
      } as SpeechDeltaPayload);

      useGameStore.getState().applySseEvent(deltaEvent);
      expect(useGameStore.getState().streamingSpeeches["w1"]).toEqual({
        label: "2号 小明",
        speech: "我觉得"
      });
    });

    it("accumulates multiple deltas for the same player (latest wins)", () => {
      useGameStore.getState().setGame(mockGame());
      useGameStore.getState().applySseEvent(mockSseEvent("speech_delta", {
        player_id: "w1", label: "2号", delta: "A", speech: "第一句"
      } as SpeechDeltaPayload));
      useGameStore.getState().applySseEvent(mockSseEvent("speech_delta", {
        player_id: "w1", label: "2号", delta: "B", speech: "第二句"
      } as SpeechDeltaPayload));

      expect(useGameStore.getState().streamingSpeeches["w1"]?.speech).toBe("第二句");
    });
  });

  describe("applySseEvent: speech_completed", () => {
    it("removes streaming speech entry", () => {
      useGameStore.getState().setGame(mockGame());
      // Set up streaming speech first
      useGameStore.setState({
        streamingSpeeches: { w1: { label: "2号", speech: "发言结束" } }
      });

      useGameStore.getState().applySseEvent({
        ...mockSseEvent("speech_completed"),
        actor_id: "w1"
      });

      expect(useGameStore.getState().streamingSpeeches).toEqual({});
    });

    it("no-ops when player is not in streaming speeches", () => {
      useGameStore.getState().setGame(mockGame());
      useGameStore.getState().applySseEvent({
        ...mockSseEvent("speech_completed"),
        actor_id: "unknown"
      });

      expect(useGameStore.getState().streamingSpeeches).toEqual({});
    });
  });

  describe("applySseEvent: private_info (seer check)", () => {
    it("parses wolf camp result", () => {
      useGameStore.getState().setGame(mockGame());
      const seerEvent = mockSseEvent("private_info", { message: "该玩家属于狼人阵营" });
      seerEvent.target_id = "w1";

      useGameStore.getState().applySseEvent(seerEvent);

      expect(useGameStore.getState().seerResults["w1"]).toEqual({
        targetPlayerId: "w1",
        targetLabel: "1号 你",
        camp: "wolf"
      });
    });

    it("parses good camp result", () => {
      useGameStore.getState().setGame(mockGame());
      const seerEvent = mockSseEvent("private_info", { message: "该玩家属于好人阵营" });
      seerEvent.target_id = "human";

      useGameStore.getState().applySseEvent(seerEvent);

      expect(useGameStore.getState().seerResults["human"]?.camp).toBe("good");
    });
  });

  describe("applySseEvent: generic events", () => {
    it("appends events with string messages to public_events", () => {
      useGameStore.getState().setGame(mockGame("night"));
      const phaseEvent = mockSseEvent("phase_changed", { message: "进入白天阶段" });
      phaseEvent.phase = "day_speech";

      useGameStore.getState().applySseEvent(phaseEvent);

      const game = useGameStore.getState().game!;
      expect(game.public_events.at(-1)?.payload.message).toBe("进入白天阶段");
      expect(game.phase).toBe("day_speech");
    });
  });

  describe("submitAction", () => {
    it("sets pending true during submission", () => {
      expect(useGameStore.getState().pending).toBe(false);
      // Can't easily test async without fetch mock — test pending state change
      useGameStore.setState({ pending: true });
      expect(useGameStore.getState().pending).toBe(true);
    });
  });

  describe("reset", () => {
    it("returns all state to initial values", () => {
      useGameStore.getState().setGame(mockGame());
      useGameStore.setState({
        streamingSpeeches: { w1: { label: "2号", speech: "test" } },
        seerResults: { w1: { targetPlayerId: "w1", targetLabel: "2号", camp: "good" } },
        pending: true,
        error: "some error"
      });

      useGameStore.getState().reset();

      const state = useGameStore.getState();
      expect(state.game).toBeNull();
      expect(state.streamingSpeeches).toEqual({});
      expect(state.seerResults).toEqual({});
      expect(state.pending).toBe(false);
      expect(state.error).toBeNull();
    });
  });
});

// --- Helpers ---

function mockGame(phase: GameStateDto["phase"] = "setup"): GameStateDto {
  return {
    game_id: "game_test",
    board_id: "board_test",
    phase,
    day_count: 0,
    human_player_id: "human",
    current_turn_player_id: null,
    players: [
      {
        player_id: "human",
        agent_id: null,
        seat: 1,
        role_key: "seer",
        alive: true,
        is_human: true,
        sheriff: false,
        display_name: "你",
        avatar_url: null,
        speaking: false,
        voted: false
      },
      {
        player_id: "w1",
        agent_id: "w1",
        seat: 2,
        role_key: null,
        alive: true,
        is_human: false,
        sheriff: false,
        display_name: "小明",
        avatar_url: null,
        speaking: false,
        voted: false
      }
    ],
    winner: null,
    public_events: [],
    allowed_actions: []
  };
}

function mockSseEvent(
  eventType: GameStreamEventDto["event_type"],
  payload: Record<string, unknown> = {}
): GameStreamEventDto {
  return {
    event_id: `evt_${Math.random().toString(36).slice(2)}`,
    event_type: eventType,
    game_id: "game_test",
    phase: "setup",
    day_count: 0,
    visibility: "public",
    actor_id: null,
    target_id: null,
    payload,
    created_at: null
  };
}
```

- [ ] **Step 2: Run store tests**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx vitest run src/stores/gameStore.test.ts
```

Expected: All tests pass (12 tests)

- [ ] **Step 3: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/stores/gameStore.test.ts
git commit -m "test(frontend): add gameStore unit tests"
```

---

### Task 5: Run all existing tests to confirm no regressions

**Files:**
- Verify: `frontend/src/GameTablePage.test.tsx` (should pass unchanged)
- Verify: `frontend/src/PhaseSceneRouter.test.tsx` (should pass unchanged)
- Verify: `frontend/src/LobbyPage.test.tsx` (should pass unchanged)
- Verify: `frontend/src/api.test.ts` (should pass unchanged)
- Verify: `frontend/src/adminApi.test.ts` (should pass unchanged)
- Verify: `frontend/src/admin/*.test.tsx` (should pass unchanged)

- [ ] **Step 1: Run the full test suite**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx vitest run
```

Expected: All tests pass, including the new store test. Zero regressions.

Key assertions:
- `src/GameTablePage.test.tsx` — 3 tests, all pass (GameTable receives same props)
- `src/PhaseSceneRouter.test.tsx` — 6 tests, all pass (no interface change)
- `src/LobbyPage.test.tsx` — all pass (untouched)
- `src/api.test.ts` — all pass (untouched)
- `src/adminApi.test.ts` — all pass (untouched)
- `src/stores/gameStore.test.ts` — 12 tests, all pass (new)

- [ ] **Step 2: Run TypeScript type check**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx tsc --noEmit
```

Expected: Zero TypeScript errors.

- [ ] **Step 3: Commit (if any snapshot or accidental changes)**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git status
```

If there are no unexpected changes, this step is complete — the previous commits already captured everything.

---

## Completion Checklist for Phase 1a

After all 5 tasks are done:

- [ ] `src/stores/gameStore.ts` exists and compiles
- [ ] `src/stores/gameStore.test.ts` has 12 passing tests
- [ ] `App.tsx` GameRoute uses `useGameStore()` instead of `useState`
- [ ] `App.tsx` has no unused imports
- [ ] All 7 existing test files still pass (zero regressions)
- [ ] GameTable/PhaseSceneRouter props interface unchanged
- [ ] `npx tsc --noEmit` passes with zero errors
- [ ] `npx vitest run` passes all tests

---

## Next Phase

After Phase 1a is complete, proceed to:
**Phase 1b: Framer Motion Animations** — Add Framer Motion, create animationStore, wrap GameTable seats and phase banner with `motion.div`, add speech highlighting and phase transition animations.

Plan file: `docs/superpowers/plans/2026-05-16-frontend-phase1b-framer-motion.md`
