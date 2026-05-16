# Frontend UX Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 frontend UX bugs: "你已出局" mislabeling, missing seer check results, and delayed night action feedback.

**Architecture:** Frontend-only changes. The backend already emits `private_info` SSE events with seer check results. We need to: (1) add `private_info` to the SSE event subscription list in `api.ts`, (2) handle it in `App.tsx` to store seer results, (3) pass them through `GameTable.tsx` to render overlay + player card badges, (4) fix `PhaseSceneRouter.tsx` to differentiate dead vs waiting.

**Tech Stack:** React 19, TypeScript, SSE (EventSource), plain CSS

---

### Task 1: Add `private_info` to SSE subscription list

**Files:**
- Modify: `frontend/src/api.ts:107-118`

- [ ] **Step 1: Add `private_info` to eventTypes array**

In `frontend/src/api.ts`, add `"private_info"` to the `eventTypes` array at line 117 (before `"game_created"`):

```typescript
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
    "night_result"
  ];
```

- [ ] **Step 2: Verify build**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.ts
git commit -m "feat: subscribe to private_info SSE events"
```

---

### Task 2: Add `SeerCheckResult` type and update `GameStreamEventDto`

**Files:**
- Modify: `frontend/src/types.ts:71-91`

- [ ] **Step 1: Add `private_info` to GameStreamEventDto event_type union**

In `frontend/src/types.ts`, add `"private_info"` to the `event_type` union in `GameStreamEventDto` (line 81, before `| string`):

```typescript
  event_type:
    | "state_snapshot"
    | "phase_changed"
    | "night_step_started"
    | "night_step_finished"
    | "speech_delta"
    | "speech_completed"
    | "current_speaker_changed"
    | "ai_thinking"
    | "private_info"
    | "game_created"
    | "night_result"
    | string;
```

- [ ] **Step 2: Add `SeerCheckResult` interface and `PrivateInfoPayload` type**

Add after `StreamingSpeechDto` (after line 107):

```typescript
export interface SeerCheckResult {
  targetPlayerId: string;
  targetLabel: string;
  camp: "good" | "wolf";
}

export interface PrivateInfoPayload {
  message: string;
}
```

- [ ] **Step 3: Verify build**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types.ts
git commit -m "feat: add SeerCheckResult and PrivateInfoPayload types"
```

---

### Task 3: Handle `private_info` events in `App.tsx`

**Files:**
- Modify: `frontend/src/App.tsx:108-188`

- [ ] **Step 1: Add seerResults state and private_info handler**

In `GameRoute()` in `frontend/src/App.tsx`:

1. Add import for `SeerCheckResult` and `PrivateInfoPayload` to the import block (line 46-62).

2. Add state after line 113 (`const [error, setError]...`):

```typescript
  const [seerResults, setSeerResults] = useState<Record<string, SeerCheckResult>>({});
```

3. Add `private_info` handler inside the `onEvent` callback, before the final `setGame` call (before line 155):

```typescript
        if (event.event_type === "private_info") {
          const payload = event.payload as unknown as PrivateInfoPayload;
          const targetId = event.target_id;
          if (!targetId) return;
          const msg = payload.message ?? "";
          const camp: "good" | "wolf" = msg.includes("狼人阵营") ? "wolf" : "good";
          // Find the target player's label from game state
          const targetPlayer = game?.players.find((p) => p.player_id === targetId);
          const targetLabel = targetPlayer ? `${targetPlayer.seat}号 ${targetPlayer.display_name}` : targetId;
          setSeerResults((prev) => ({
            ...prev,
            [targetId]: { targetPlayerId: targetId, targetLabel, camp }
          }));
          return;
        }
```

4. Pass `seerResults` to `GameTable` (line 187):

Change:
```typescript
  return <GameTable game={game} onSubmitAction={handleAction} pending={pending} streamingSpeeches={streamingSpeeches} />;
```
To:
```typescript
  return <GameTable game={game} onSubmitAction={handleAction} pending={pending} streamingSpeeches={streamingSpeeches} seerResults={seerResults} />;
```

5. Add `SeerCheckResult` to the import from `./types`.

- [ ] **Step 2: Verify build**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: handle private_info SSE events for seer results"
```

---

### Task 4: Fix "你已出局" mislabeling in PhaseSceneRouter

**Files:**
- Modify: `frontend/src/PhaseSceneRouter.tsx:5-9, 42-44, 102-104, 125-129`

- [ ] **Step 1: Add `isAlive` helper prop to determine player alive status**

Change `PhaseSceneRouterProps` interface (lines 5-9) to also receive the human player's alive status:

```typescript
interface PhaseSceneRouterProps {
  game: GameStateDto;
  onSubmitAction: (action: SubmitActionInput) => Promise<void>;
  pending: boolean;
}
```

Add a helper function after the component destructuring (after line 17) to get the human player's alive status:

```typescript
  const humanPlayer = game.players.find((p) => p.player_id === game.human_player_id);
  const isAlive = humanPlayer?.alive ?? true;
```

- [ ] **Step 2: Fix night phase ObserverScene message (line 44)**

Change:
```typescript
      return <ObserverScene kicker="NIGHT" title="夜晚行动" message="你已出局，正在等待夜晚结算。" />;
```
To:
```typescript
      return <ObserverScene kicker="NIGHT" title="夜晚行动" message={isAlive ? "等待其他玩家行动中..." : "你已出局，正在等待夜晚结算。"} />;
```

- [ ] **Step 3: Fix day_speech phase ObserverScene message (line 104)**

Change:
```typescript
      return <ObserverScene kicker="SPEECH" title="白天发言" message="你已出局，正在旁听其他玩家发言。" />;
```
To:
```typescript
      return <ObserverScene kicker="SPEECH" title="白天发言" message={isAlive ? "等待其他玩家发言中..." : "你已出局，正在旁听其他玩家发言。"} />;
```

- [ ] **Step 4: Fix exile_vote phase ObserverScene message (line 129)**

Change:
```typescript
      return <ObserverScene kicker="VOTE" title="放逐投票" message="你已出局，正在等待其他玩家投票。" />;
```
To:
```typescript
      return <ObserverScene kicker="VOTE" title="放逐投票" message={isAlive ? "等待其他玩家投票中..." : "你已出局，正在等待其他玩家投票。"} />;
```

- [ ] **Step 5: Verify build**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/PhaseSceneRouter.tsx
git commit -m "fix: show correct message for alive players waiting in speech/vote/night"
```

---

### Task 5: Render seer results in GameTable — player card badges + full-screen overlay

**Files:**
- Modify: `frontend/src/GameTable.tsx:1-96`

- [ ] **Step 1: Update GameTableProps to accept seerResults**

Add import of `SeerCheckResult` from `./types`. Update the `GameTableProps` interface (lines 4-9):

```typescript
interface GameTableProps {
  game: GameStateDto;
  onSubmitAction: (action: SubmitActionInput) => Promise<void>;
  pending: boolean;
  streamingSpeeches?: Record<string, StreamingSpeechDto>;
  seerResults?: Record<string, SeerCheckResult>;
}
```

Update the destructuring (line 23):

```typescript
export function GameTable({ game, onSubmitAction, pending, streamingSpeeches = {}, seerResults = {} }: GameTableProps) {
```

- [ ] **Step 2: Add overlay state for new seer results**

Add `useState` and `useEffect` imports (update line 1). Add after the streaming speech entries memo (line 24):

```typescript
  const [overlayResult, setOverlayResult] = useState<SeerCheckResult | null>(null);
  const [prevResultCount, setPrevResultCount] = useState(0);
  const resultKeys = Object.keys(seerResults);

  if (resultKeys.length > prevResultCount) {
    setPrevResultCount(resultKeys.length);
    const latestKey = resultKeys[resultKeys.length - 1];
    setOverlayResult(seerResults[latestKey]);
    setTimeout(() => setOverlayResult(null), 3500);
  }
```

- [ ] **Step 3: Add seer result badges to player cards**

In the `.seat-tags` div (line 50-55), add after the `{player.voted && ...}` line:

```typescript
                {seerResults[player.player_id] && (
                  <span className={`seer-badge ${seerResults[player.player_id].camp}`}>
                    {seerResults[player.player_id].camp === "good" ? "好" : "狼"}
                  </span>
                )}
```

- [ ] **Step 4: Add overlay JSX**

Add before the closing `</main>` tag (before line 83):

```typescript
      {overlayResult && (
        <div className="seer-overlay" onClick={() => setOverlayResult(null)}>
          <div className={`seer-overlay-card ${overlayResult.camp}`}>
            <p className="seer-overlay-label">查验结果</p>
            <h2>{overlayResult.targetLabel}</h2>
            <p className="seer-overlay-camp">
              {overlayResult.camp === "good" ? "好人阵营" : "狼人阵营"}
            </p>
          </div>
        </div>
      )}
```

- [ ] **Step 5: Verify build**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/GameTable.tsx
git commit -m "feat: render seer check results as overlay + player card badges"
```

---

### Task 6: Add CSS styles for seer overlay and badges

**Files:**
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add seer overlay styles**

Append at end of `styles.css` (before the admin section, after line 675):

```css
/* Seer check result overlay */
.seer-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.7);
  animation: seer-overlay-in 0.3s ease-out;
  cursor: pointer;
}

.seer-overlay-card {
  text-align: center;
  padding: 48px 64px;
  border-radius: 16px;
  animation: seer-card-pop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.seer-overlay-card.good {
  background: linear-gradient(135deg, rgba(34, 139, 34, 0.9), rgba(46, 125, 50, 0.85));
  border: 2px solid rgba(100, 200, 100, 0.5);
  box-shadow: 0 0 60px rgba(46, 125, 50, 0.4);
}

.seer-overlay-card.wolf {
  background: linear-gradient(135deg, rgba(178, 34, 34, 0.9), rgba(142, 36, 26, 0.85));
  border: 2px solid rgba(255, 100, 80, 0.5);
  box-shadow: 0 0 60px rgba(178, 34, 34, 0.4);
}

.seer-overlay-label {
  margin: 0 0 8px;
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.7);
}

.seer-overlay-card h2 {
  margin: 0 0 12px;
  font-size: 2.2rem;
  color: #fff;
}

.seer-overlay-camp {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 800;
  color: #fff;
}

.seer-badge {
  font-weight: 800;
  font-size: 0.75rem;
}

.seer-badge.good {
  border-color: rgba(46, 125, 50, 0.7);
  background: rgba(46, 125, 50, 0.3);
  color: #6fcf6f;
}

.seer-badge.wolf {
  border-color: rgba(178, 34, 34, 0.7);
  background: rgba(178, 34, 34, 0.3);
  color: #ff8a80;
}

@keyframes seer-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes seer-card-pop {
  from { opacity: 0; transform: scale(0.7); }
  to { opacity: 1; transform: scale(1); }
}
```

- [ ] **Step 2: Verify build**

Run: `cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/styles.css
git commit -m "feat: add CSS for seer check overlay and player card badges"
```

---

### Task 7: Run frontend build and verify

- [ ] **Step 1: Run full frontend build**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend && npm run build
```
Expected: Build succeeds with no errors.

- [ ] **Step 2: Run frontend tests**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend && npx vitest run
```
Expected: All tests pass.
