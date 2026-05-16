# Phase 1e: TailwindCSS Migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single 755-line `styles.css` with Tailwind CSS v4 utility classes, preserving the dark werewolf theme (gold #D7A756, dark brown #11100F, off-white #F7EFE1).

**Architecture:** Tailwind CSS v4 integrates via `@tailwindcss/vite` plugin (no PostCSS config needed). Theme values are defined with `@theme` in the CSS entry. Each component's className strings are replaced with Tailwind utility equivalents. Existing component logic and test assertions are preserved — only visual classes change.

**Tech Stack:** tailwindcss ^4.x, @tailwindcss/vite ^4.x, Vite 7.x

**Pre-requisites:** Phases 1a-1d complete.

**What does NOT change:**
- Component logic (zero JS/TSX logic changes)
- Props interfaces
- Test assertions (getByRole, getByText, getByLabelText still work with Tailwind)
- API layer, stores, hooks — zero changes
- Admin pages (migrated in a follow-up phase)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/package.json` | **Modify** | Add tailwindcss + @tailwindcss/vite |
| `frontend/vite.config.ts` | **Modify** | Add @tailwindcss/vite plugin |
| `frontend/src/index.css` | **Create** | Tailwind entry: @import + @theme |
| `frontend/src/main.tsx` | **Modify** | Import index.css instead of styles.css |
| `frontend/src/App.tsx` | **Modify** | Replace className strings |
| `frontend/src/GameTable.tsx` | **Modify** | Replace className strings |
| `frontend/src/PhaseSceneRouter.tsx` | **Modify** | Replace className strings |
| `frontend/src/LobbyPage.tsx` | **Modify** | Replace className strings |
| `frontend/src/styles.css` | **Delete** | No longer needed |

---

### Task 1: Install Tailwind CSS v4

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install Tailwind**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npm install tailwindcss @tailwindcss/vite
```

- [ ] **Step 2: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): add tailwindcss v4 and vite plugin"
```

---

### Task 2: Configure Tailwind with Vite and create CSS entry

**Files:**
- Modify: `frontend/vite.config.ts`
- Create: `frontend/src/index.css`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Add @tailwindcss/vite to vite.config.ts**

Current vite.config.ts:
```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./vitest.setup.ts",
    globals: true
  }
});
```

Add the tailwind plugin:
```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [tailwindcss(), react()],
  test: {
    environment: "jsdom",
    setupFiles: "./vitest.setup.ts",
    globals: true
  }
});
```

- [ ] **Step 2: Create index.css with Tailwind imports and theme**

Create `frontend/src/index.css`:

```css
@import "tailwindcss";

/* ── Dark Werewolf Theme ─────────────────────────────────── */
@theme {
  --color-gold: #D7A756;
  --color-gold-dim: #A88A4A;
  --color-warm-bg: #1A1714;
  --color-warm-card: #2A2520;
  --color-warm-border: #3A3228;
  --color-text: #F7EFE1;
  --color-text-dim: #CABCA5;
  --color-text-muted: #8A7E6E;
  --color-red-werewolf: #8E241A;
  --color-red-bg: #3A1818;
  --color-green-seer: #22C55E;
  --color-green-bg: #1A3828;
  --color-blue-night: #3B82F6;
  --color-blue-bg: #1A2030;
  --color-purple-llm: #A855F7;
  --color-purple-bg: #2A1A38;
  --color-amber: #F59E0B;
  --color-amber-bg: #3A2818;

  --font-family-sans: "Inter", system-ui, -apple-system, sans-serif;
}

/* ── Base overrides ─────────────────────────────────────── */
body {
  background-color: var(--color-warm-bg);
  color: var(--color-text);
  font-family: var(--font-family-sans);
  background-image:
    radial-gradient(ellipse 80% 50% at 50% -10%, rgba(215, 167, 86, 0.05), transparent),
    radial-gradient(ellipse 60% 40% at 50% 100%, rgba(142, 36, 26, 0.08), transparent);
  min-height: 100vh;
}

/* ── Scrollbar ──────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--color-warm-bg); }
::-webkit-scrollbar-thumb { background: var(--color-warm-border); border-radius: 3px; }

/* ── Button base styles (Tailwind doesn't cover these well) */
button {
  cursor: pointer;
  font-family: inherit;
}

/* ── Seer overlay keyframe (Tailwind doesn't do keyframes) ──
   Note: if Framer Motion handles seer overlay animation (Phase 1b),
   remove this. Otherwise keep as fallback. */
@keyframes seer-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes seer-card-pop {
  from { transform: scale(0.5); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
```

- [ ] **Step 3: Update main.tsx to import index.css**

In `frontend/src/main.tsx`, change:
```typescript
import "./styles.css";
```
To:
```typescript
import "./index.css";
```

- [ ] **Step 4: Verify Vite starts with Tailwind**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx vite build 2>&1 | head -20
```

Expected: Build succeeds. Tailwind processes the CSS.

- [ ] **Step 5: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/vite.config.ts frontend/src/index.css frontend/src/main.tsx
git commit -m "feat(frontend): configure Tailwind CSS v4 with dark werewolf theme"
```

---

### Task 3: Migrate GameTable.tsx to Tailwind classes

**Files:**
- Modify: `frontend/src/GameTable.tsx`

Replace all className strings with Tailwind utilities. The CSS classes being replaced:

| Old CSS class | Tailwind equivalent |
|---|---|
| `.game-table` | `flex flex-col gap-6 max-w-7xl mx-auto px-4 py-6` |
| `.phase-banner` | `flex justify-between items-center p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]` |
| `.scene-kicker` | `text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-1` |
| `.phase-meta` | `flex gap-4 text-sm text-[var(--color-text-dim)]` |
| `.table-layout` | `grid grid-cols-[1fr_280px] gap-6` |
| `.seat-ring` | `grid grid-cols-3 gap-3` |
| `.player-seat` | `flex flex-col items-center gap-2 p-4 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)] transition-all` |
| `.player-seat.is-speaking` | `border-[var(--color-gold)] shadow-[0_0_24px_rgba(215,167,86,0.3)]` |
| `.player-seat.is-dead` | `opacity-50` |
| `.avatar` | `w-12 h-12 rounded-full bg-[var(--color-warm-border)] flex items-center justify-center text-lg font-bold text-[var(--color-text-dim)] overflow-hidden` |
| `.seat-tags` | `flex flex-wrap gap-1 justify-center` |
| `.event-log` | `flex flex-col gap-2 p-4 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)] max-h-[calc(100vh-220px)] overflow-y-auto` |
| `.panel-title` | `text-sm font-semibold text-[var(--color-text-dim)] pb-2 border-b border-[var(--color-warm-border)]` |
| `.empty-state` | `text-sm text-[var(--color-text-muted)] italic` |
| `.streaming-event` | `text-sm text-[var(--color-gold)]` |
| `.seer-overlay` | `fixed inset-0 bg-black/60 flex items-center justify-center z-50` |
| `.seer-badge.good` | `bg-[var(--color-green-bg)] text-[var(--color-green-seer)]` |
| `.seer-badge.wolf` | `bg-[var(--color-red-bg)] text-red-400` |

- [ ] **Step 1: Replace all className strings in GameTable.tsx**

Replace the component JSX (lines 43-116) with Tailwind classNames:

```tsx
return (
  <main className="flex flex-col gap-6 max-w-7xl mx-auto px-4 py-6">
    <motion.header
      className="flex justify-between items-center p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]"
      key={`${game.phase}-${game.day_count}`}
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, type: "spring", stiffness: 150 }}
    >
      <div>
        <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-1">AI WEREWOLF ROOM</p>
        <h1 className="text-2xl font-bold">{phaseLabels[game.phase]}</h1>
      </div>
      <div className="flex gap-4 text-sm text-[var(--color-text-dim)]">
        <span>第 {game.day_count} 天</span>
        <span>{game.winner ? `胜利：${game.winner}` : "对局进行中"}</span>
      </div>
    </motion.header>

    <section className="grid grid-cols-[1fr_280px] gap-6 max-md:grid-cols-1">
      <div className="grid grid-cols-3 gap-3" aria-label="玩家座位">
        {game.players.map((player, index) => (
          <motion.article
            className={`flex flex-col items-center gap-2 p-4 rounded-xl border transition-all
              ${player.alive ? "border-[var(--color-warm-border)] bg-[var(--color-warm-card)]" : "border-[var(--color-warm-border)] bg-[var(--color-warm-card)] opacity-50"}
              ${player.speaking ? "!border-[var(--color-gold)]" : ""}
            `}
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
            <div className="w-12 h-12 rounded-full bg-[var(--color-warm-border)] flex items-center justify-center text-lg font-bold text-[var(--color-text-dim)] overflow-hidden" aria-hidden="true">
              {player.avatar_url ? <img src={player.avatar_url} alt="" /> : player.display_name.slice(0, 1)}
            </div>
            <div>
              <strong>{player.display_name}</strong>
              <p>{player.seat}号位</p>
            </div>
            <div className="flex flex-wrap gap-1 justify-center">
              {player.role_key && <span className="text-xs px-2 py-0.5 rounded bg-[var(--color-warm-border)]">{roleLabel(player.role_key)}</span>}
              {player.sheriff && <span className="text-xs px-2 py-0.5 rounded bg-[var(--color-amber-bg)] text-[var(--color-amber)]">警长</span>}
              {!player.alive && <span className="text-xs px-2 py-0.5 rounded bg-[var(--color-red-bg)] text-red-400">出局</span>}
              {player.voted && <span className="text-xs px-2 py-0.5 rounded bg-[var(--color-blue-bg)] text-[var(--color-blue-night)]">已投票</span>}
              {seerResults[player.player_id] && (
                <span className={`text-xs px-2 py-0.5 rounded ${seerResults[player.player_id].camp === "good" ? "bg-[var(--color-green-bg)] text-[var(--color-green-seer)]" : "bg-[var(--color-red-bg)] text-red-400"}`}>
                  {seerResults[player.player_id].camp === "good" ? "好" : "狼"}
                </span>
              )}
            </div>
          </motion.article>
        ))}
      </div>

      <aside className="flex flex-col gap-2 p-4 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)] max-h-[calc(100vh-220px)] overflow-y-auto" aria-label="事件时间线">
        <div className="text-sm font-semibold text-[var(--color-text-dim)] pb-2 border-b border-[var(--color-warm-border)]">事件时间线</div>
        {game.public_events.length === 0 ? (
          <motion.p className="text-sm text-[var(--color-text-muted)] italic" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            等待第一条事件。
          </motion.p>
        ) : (
          game.public_events.map((event, index) => (
            <motion.p
              key={`${event.event_type}-${index}`}
              className="text-sm"
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: Math.min(index * 0.03, 0.5), duration: 0.25 }}
            >
              <span className="text-xs text-[var(--color-text-muted)] mr-2">{event.event_type}</span>
              {event.payload.message}
            </motion.p>
          ))
        )}
        <AnimatePresence>
          {streamingSpeechEntries.map(([playerId, value]) => (
            <motion.p
              className="text-sm text-[var(--color-gold)]"
              key={`streaming-${playerId}`}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
            >
              <span className="text-xs text-[var(--color-text-muted)] mr-2">speech_delta</span>
              {value.label}：{value.speech}
            </motion.p>
          ))}
        </AnimatePresence>
      </aside>
    </section>

    <PhaseSceneRouter game={game} onSubmitAction={onSubmitAction} pending={pending} />

    <AnimatePresence>
      {overlayResult && (
        <motion.div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          onClick={() => setOverlayResult(null)}
        >
          <motion.div
            className={`p-8 rounded-2xl text-center min-w-[280px] backdrop-blur ${
              overlayResult.camp === "good"
                ? "bg-[var(--color-green-bg)]/90 border-2 border-[var(--color-green-seer)]"
                : "bg-[var(--color-red-bg)]/90 border-2 border-red-400"
            }`}
            initial={{ scale: 0.5, opacity: 0, y: 30 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.8, opacity: 0, y: -20 }}
            transition={{ type: "spring", stiffness: 300, damping: 20 }}
          >
            <p className="text-sm text-[var(--color-text-dim)] mb-2">查验结果</p>
            <h2 className="text-2xl font-bold mb-2">{overlayResult.targetLabel}</h2>
            <p className={`text-lg font-semibold ${overlayResult.camp === "good" ? "text-[var(--color-green-seer)]" : "text-red-400"}`}>
              {overlayResult.camp === "good" ? "好人阵营" : "狼人阵营"}
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  </main>
);
```

- [ ] **Step 2: Verify tests pass**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx vitest run src/GameTablePage.test.tsx
```

Expected: 3 tests pass. DOM queries (getByRole, getByText) not affected by className changes.

- [ ] **Step 3: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/GameTable.tsx
git commit -m "refactor(frontend): migrate GameTable className to Tailwind utilities"
```

---

### Task 4: Migrate PhaseSceneRouter.tsx, App.tsx, and LobbyPage.tsx

**Files:**
- Modify: `frontend/src/PhaseSceneRouter.tsx`
- Modify: `frontend/src/App.tsx` (StatusScreen component only)
- Modify: `frontend/src/LobbyPage.tsx`

- [ ] **Step 1: Migrate PhaseSceneRouter.tsx classNames**

Replace all className strings. Key CSS-to-Tailwind mappings:

| Old | New Tailwind |
|---|---|
| `.scene-panel` | `p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]` |
| `.scene-panel.night-scene` | Add: `border-[var(--color-blue-night)]` |
| `.scene-panel.result-scene` | Add: `border-[var(--color-gold)]` |
| `.scene-kicker` | `text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-2` |
| `.speech-input` | `w-full p-3 rounded-lg border border-[var(--color-warm-border)] bg-[var(--color-warm-bg)] text-[var(--color-text)] resize-y min-h-[100px]` |
| `.target-grid` | `grid grid-cols-2 gap-2` |
| `.target-option` | `flex items-center gap-2 p-3 rounded-lg border border-[var(--color-warm-border)] hover:border-[var(--color-gold)] bg-[var(--color-warm-bg)] cursor-pointer` |
| `.action-row` | `flex gap-3` |
| `.primary-action` | `px-6 py-3 rounded-lg bg-[var(--color-gold)] text-[var(--color-warm-bg)] font-semibold hover:bg-[var(--color-gold-dim)] disabled:opacity-50` |
| `.ghost-action` | `px-6 py-3 rounded-lg border border-[var(--color-warm-border)] bg-transparent text-[var(--color-text)] font-semibold hover:bg-[var(--color-warm-card)] disabled:opacity-50` |
| `.primary-link` | `px-6 py-3 rounded-lg bg-[var(--color-gold)] text-[var(--color-warm-bg)] font-semibold hover:bg-[var(--color-gold-dim)] no-underline text-center inline-block` |
| `.role-reveal` | `grid grid-cols-2 gap-2 mt-4` |

Replace the PhaseSceneRouter JSX with Tailwind equivalents. The `ObserverScene` component:

```tsx
function ObserverScene({ kicker, title, message }: { kicker: string; title: string; message: string }) {
  return (
    <section className="p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]">
      <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-2">{kicker}</p>
      <h2>{title}</h2>
      <p>{message}</p>
    </section>
  );
}
```

For each phase section, replace the `className`:

- setup phase section: `className="p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]"`
- night scene section: `className="p-6 rounded-xl border border-[var(--color-blue-night)] bg-[var(--color-warm-card)]"`
- day_announcement section: `className="p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]"`
- day_speech section: `className="p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]"`
- exile_vote section: `className="p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]"`
- last_words section: `className="p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]"`
- game_over section: `className="p-6 rounded-xl border border-[var(--color-gold)] bg-[var(--color-warm-card)]"`

- [ ] **Step 2: Migrate App.tsx StatusScreen**

```tsx
function StatusScreen({ title, detail }: { title: string; detail: string }) {
  return (
    <main className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center px-4">
      <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)]">AI WEREWOLF</p>
      <h1 className="text-3xl font-bold">{title}</h1>
      <p className="text-[var(--color-text-dim)]">{detail}</p>
    </main>
  );
}
```

- [ ] **Step 3: Migrate LobbyPage.tsx classNames**

Replace CSS classes with Tailwind. Key mappings:

| Old | New Tailwind |
|---|---|
| `.lobby-shell` | `flex flex-col items-center gap-8 max-w-4xl mx-auto px-4 py-10` |
| `.lobby-hero` | `text-center mb-4` |
| `.lobby-grid` | `grid grid-cols-3 gap-6 w-full max-md:grid-cols-1` |
| `.config-panel` | `p-5 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]` |
| `.start-panel` | `p-5 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)] col-span-3 max-md:col-span-1` |
| `.board-list` | `flex flex-col gap-2` |
| `.board-card` | `p-3 rounded-lg border cursor-pointer transition-all` + active/inactive states |
| `.agent-list` | `flex flex-col gap-2 max-h-[300px] overflow-y-auto` |
| `.agent-card` | `flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all` |

- [ ] **Step 4: Run all tests**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx vitest run
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/PhaseSceneRouter.tsx frontend/src/App.tsx frontend/src/LobbyPage.tsx
git commit -m "refactor(frontend): migrate PhaseSceneRouter, App, LobbyPage to Tailwind utilities"
```

---

### Task 5: Delete styles.css and final verification

**Files:**
- Delete: `frontend/src/styles.css`

- [ ] **Step 1: Delete styles.css**

```bash
rm /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend/src/styles.css
```

- [ ] **Step 2: Run full test suite and type check**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx tsc --noEmit
npx vitest run
```

Expected: Zero TypeScript errors, all tests pass.

- [ ] **Step 3: Verify build succeeds**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx vite build
```

Expected: Build succeeds, output in `dist/`. Tailwind CSS is included in the bundle.

- [ ] **Step 4: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git rm frontend/src/styles.css
git commit -m "refactor(frontend): remove styles.css, fully migrated to Tailwind CSS"
```

---

## Completion Checklist for Phase 1e

- [ ] `tailwindcss` + `@tailwindcss/vite` installed
- [ ] `vite.config.ts` includes tailwind plugin
- [ ] `src/index.css` defines Tailwind imports + @theme with dark werewolf palette
- [ ] `src/main.tsx` imports index.css (not styles.css)
- [ ] `GameTable.tsx` uses Tailwind utilities for all classNames
- [ ] `PhaseSceneRouter.tsx` uses Tailwind utilities
- [ ] `App.tsx` StatusScreen uses Tailwind utilities
- [ ] `LobbyPage.tsx` uses Tailwind utilities
- [ ] `styles.css` deleted
- [ ] `npx tsc --noEmit` passes
- [ ] `npx vitest run` passes (all tests)
- [ ] `npx vite build` succeeds

---

## Phase 1 Complete

After all 5 sub-phases (1a-1e) are done, the MVP is complete:

| Phase | What changed | Key technology |
|-------|-------------|----------------|
| 1a | State management moved from useState to Zustand | zustand |
| 1b | CSS animations replaced by Framer Motion | framer-motion |
| 1c | AI speech audio playback via TTS | edge-tts, Web Audio API |
| 1d | SSE replaced by Socket.IO bidirectional transport | python-socketio, socket.io-client |
| 1e | 755-line CSS replaced by Tailwind utilities | tailwindcss |

**Verification checklist:**
- [ ] Game starts (lobby → create game → setup → night → speech → vote → game over)
- [ ] AI speeches play audio via TTS
- [ ] Player seats animate on mount, speaking player glows
- [ ] Phase banner animates on transitions
- [ ] Event log entries stagger in
- [ ] Seer overlay animates in/out
- [ ] Socket.IO auto-reconnects on disconnect
- [ ] Actions submit via Socket.IO (or REST fallback)
- [ ] All unit tests pass
- [ ] TypeScript compiles clean

---

## Next Phases

**Phase 2: Gamification** — PixiJS game rendering, XState state machine, particle effects, vote animations (3 plan files).

**Phase 3: Productization** — Live2D characters, CosyVoice TTS, WebRTC voice chat (3 plan files).

Phase 2 & 3 plans will be written after Phase 1 is complete.
