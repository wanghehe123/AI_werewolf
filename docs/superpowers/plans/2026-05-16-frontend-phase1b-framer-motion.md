# Phase 1b: Framer Motion Animations

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Framer Motion-powered animations to the game UI — speaking highlight, phase transitions, seer overlay, event log entries — replacing raw CSS keyframes with declarative React animations.

**Architecture:** Wrap existing DOM elements in `motion.div` with `AnimatePresence`. Speaking players get `motion.div` with `scale` + `boxShadow` animation. Phase banner uses `layoutId` for smooth transitions. Seer overlay uses `AnimatePresence` with `exit` animation (replacing CSS `@keyframes`). Event log entries use staggered `motion.p` entries. Zero logic changes — pure presentation layer.

**Tech Stack:** framer-motion ^11.x, React 19, TypeScript 5.9

**Pre-requisite:** Phase 1a (Zustand) complete. This phase depends on `useGameStore` from Phase 1a — GameTable must receive game state via props from the store-connected parent.

**What does NOT change:**
- App.tsx — zero changes (props interface unchanged)
- PhaseSceneRouter.tsx — zero changes
- api.ts — zero changes
- types.ts — zero changes
- gameStore.ts — zero changes
- Admin pages — zero changes

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/package.json` | **Modify** | Add framer-motion dependency |
| `frontend/src/GameTable.tsx` | **Modify** | Wrap seats/spseer overlay/events with motion components |
| `frontend/src/styles.css` | **Modify** | Remove CSS `@keyframes seer-overlay-in` and `seer-card-pop` (replaced by Framer Motion) |

---

### Task 1: Install framer-motion

**Files:**
- Modify: `frontend/package.json` (via npm install)

- [ ] **Step 1: Install framer-motion**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npm install framer-motion
```

- [ ] **Step 2: Verify importable**

```bash
node -e "const { motion } = require('framer-motion'); console.log('OK')"
```

If the above fails because framer-motion is ESM-only, use:

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
node --input-type=module -e "import { motion } from 'framer-motion'; console.log('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): add framer-motion dependency"
```

---

### Task 2: Animate player seats with speaking highlight

**Files:**
- Modify: `frontend/src/GameTable.tsx:55-78` (the seat ring section)

Replace the plain `<article>` seat with a `motion.article` that animates scale and glow when `player.speaking` is true. Also add stagger animation for initial seat appearance.

- [ ] **Step 1: Add framer-motion import to GameTable.tsx**

At the top of `GameTable.tsx` (after existing imports), add:

```typescript
import { motion, AnimatePresence } from "framer-motion";
```

- [ ] **Step 2: Replace the seat article with motion.article**

Replace lines 57-78 (the `.player-seat` article and its contents) with:

```tsx
{game.players.map((player, index) => (
  <motion.article
    className={`player-seat ${player.alive ? "" : "is-dead"} ${player.speaking ? "is-speaking" : ""}`}
    key={player.player_id}
    initial={{ opacity: 0, scale: 0.8 }}
    animate={{
      opacity: 1,
      scale: 1,
      boxShadow: player.speaking
        ? "0 0 24px rgba(215, 167, 86, 0.6)"
        : "0 0 0px rgba(215, 167, 86, 0)"
    }}
    transition={{
      opacity: { delay: index * 0.08, duration: 0.3 },
      scale: { delay: index * 0.08, duration: 0.3, type: "spring", stiffness: 200 },
      boxShadow: { duration: 0.4 }
    }}
  >
    <div className="avatar" aria-hidden="true">
      {player.avatar_url ? <img src={player.avatar_url} alt="" /> : player.display_name.slice(0, 1)}
    </div>
    <div>
      <strong>{player.display_name}</strong>
      <p>{player.seat}号位</p>
    </div>
    <div className="seat-tags">
      {player.role_key && <span>{roleLabel(player.role_key)}</span>}
      {player.sheriff && <span>警长</span>}
      {!player.alive && <span>出局</span>}
      {player.voted && <span>已投票</span>}
      {seerResults[player.player_id] && (
        <span className={`seer-badge ${seerResults[player.player_id].camp}`}>
          {seerResults[player.player_id].camp === "good" ? "好" : "狼"}
        </span>
      )}
    </div>
  </motion.article>
))}
```

- [ ] **Step 3: Verify existing tests still pass**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx vitest run src/GameTablePage.test.tsx
```

Expected: 3 tests pass. The `motion.article` renders an `<article>` element under the hood, so DOM queries (`getByRole`, `getByText`) work identically.

- [ ] **Step 4: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/GameTable.tsx
git commit -m "feat(frontend): animate player seats with Framer Motion speaking highlight"
```

---

### Task 3: Animate phase banner with smooth transition

**Files:**
- Modify: `frontend/src/GameTable.tsx:44-53` (the phase-banner header)

Replace the static `<header>` with a `<motion.header>` that animates on phase/day_count changes using `layoutId`.

- [ ] **Step 1: Replace phase banner header with motion.header**

Replace lines 44-53 with:

```tsx
<motion.header
  className="phase-banner"
  key={`${game.phase}-${game.day_count}`}
  initial={{ opacity: 0, y: -20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.4, type: "spring", stiffness: 150 }}
>
  <div>
    <p className="scene-kicker">AI WEREWOLF ROOM</p>
    <h1>{phaseLabels[game.phase]}</h1>
  </div>
  <div className="phase-meta">
    <span>第 {game.day_count} 天</span>
    <span>{game.winner ? `胜利：${game.winner}` : "对局进行中"}</span>
  </div>
</motion.header>
```

- [ ] **Step 2: Verify test**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx vitest run src/GameTablePage.test.tsx
```

Expected: `getByRole("heading", { name: "准备开局", level: 1 })` still finds the heading (motion.header renders a `<header>` element).

- [ ] **Step 3: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/GameTable.tsx
git commit -m "feat(frontend): animate phase banner with Framer Motion transitions"
```

---

### Task 4: Replace CSS seer overlay keyframes with Framer Motion AnimatePresence

**Files:**
- Modify: `frontend/src/GameTable.tsx:104-114` (the seer overlay section)
- Modify: `frontend/src/styles.css` (remove `@keyframes seer-overlay-in` and `seer-card-pop`)

- [ ] **Step 1: Replace seer overlay JSX with motion components**

Replace lines 104-114 with:

```tsx
<AnimatePresence>
  {overlayResult && (
    <motion.div
      className="seer-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
      onClick={() => setOverlayResult(null)}
    >
      <motion.div
        className={`seer-overlay-card ${overlayResult.camp}`}
        initial={{ scale: 0.5, opacity: 0, y: 30 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.8, opacity: 0, y: -20 }}
        transition={{ type: "spring", stiffness: 300, damping: 20 }}
      >
        <p className="seer-overlay-label">查验结果</p>
        <h2>{overlayResult.targetLabel}</h2>
        <p className="seer-overlay-camp">
          {overlayResult.camp === "good" ? "好人阵营" : "狼人阵营"}
        </p>
      </motion.div>
    </motion.div>
  )}
</AnimatePresence>
```

- [ ] **Step 2: Remove CSS keyframes that are now replaced**

In `frontend/src/styles.css`, find and remove these keyframe blocks:

```css
@keyframes seer-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes seer-card-pop {
  from { transform: scale(0.5); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
```

Also update the `.seer-overlay` and `.seer-overlay-card` CSS rules to remove the `animation` property:

**Before (seer-overlay):**
```css
.seer-overlay {
  /* ... other props ... */
  animation: seer-overlay-in 0.3s ease-out;
}
```

**After:**
```css
.seer-overlay {
  /* ... keep all other props, remove animation: line ... */
}
```

**Before (seer-overlay-card):**
```css
.seer-overlay-card {
  /* ... other props ... */
  animation: seer-card-pop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
```

**After:**
```css
.seer-overlay-card {
  /* ... keep all other props, remove animation: line ... */
}
```

- [ ] **Step 3: Verify tests pass**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx vitest run src/GameTablePage.test.tsx
```

Expected: 3 tests pass.

- [ ] **Step 4: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/GameTable.tsx frontend/src/styles.css
git commit -m "feat(frontend): replace CSS seer overlay keyframes with Framer Motion AnimatePresence"
```

---

### Task 5: Animate event log entries with staggered entry

**Files:**
- Modify: `frontend/src/GameTable.tsx:81-98` (the event log section)

- [ ] **Step 1: Replace event log entries with motion.p staggered items**

Replace lines 81-98 (the event log aside contents) with:

```tsx
<aside className="event-log" aria-label="事件时间线">
  <div className="panel-title">事件时间线</div>
  {game.public_events.length === 0 ? (
    <motion.p
      className="empty-state"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      等待第一条事件。
    </motion.p>
  ) : (
    game.public_events.map((event, index) => (
      <motion.p
        key={`${event.event_type}-${index}`}
        initial={{ opacity: 0, x: -16 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: Math.min(index * 0.03, 0.5), duration: 0.25 }}
      >
        <span>{event.event_type}</span>
        {event.payload.message}
      </motion.p>
    ))
  )}
  <AnimatePresence>
    {streamingSpeechEntries.map(([playerId, value]) => (
      <motion.p
        className="streaming-event"
        key={`streaming-${playerId}`}
        initial={{ opacity: 0, x: -16 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0 }}
      >
        <span>speech_delta</span>
        {value.label}：{value.speech}
      </motion.p>
    ))}
  </AnimatePresence>
</aside>
```

- [ ] **Step 2: Verify tests pass**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx vitest run src/GameTablePage.test.tsx
```

Expected: 3 tests pass. The streaming speech test (`renders streaming speech deltas as a temporary timeline item`) still finds `"speech_delta"` and `"2号 小明：我正在实时发言"` in the DOM.

- [ ] **Step 3: Run all tests**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx vitest run
```

Expected: All tests pass (store tests, component tests, API tests).

- [ ] **Step 4: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/GameTable.tsx
git commit -m "feat(frontend): animate event log entries with Framer Motion staggered entry"
```

---

## Completion Checklist for Phase 1b

- [ ] `framer-motion` installed in package.json
- [ ] Player seats animate on mount with staggered spring; speaking player has gold glow
- [ ] Phase banner animates on phase/day change with spring transition
- [ ] Seer overlay uses `AnimatePresence` with enter/exit animations (CSS keyframes removed)
- [ ] Event log entries stagger in; streaming speeches animate in/out
- [ ] All 7 test files pass (zero regressions)
- [ ] `npx tsc --noEmit` passes with zero errors

---

## Next Phase

After Phase 1b is complete, proceed to:
**Phase 1c: TTS Audio Pipeline** — Add Edge-TTS backend integration, streaming audio playback via Web Audio API, audio queue management, and subtitle sync.

Plan file: `docs/superpowers/plans/2026-05-16-frontend-phase1c-tts-audio.md`
