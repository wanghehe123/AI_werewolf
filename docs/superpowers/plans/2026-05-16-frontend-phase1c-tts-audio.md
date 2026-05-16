# Phase 1c: TTS Audio Pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Edge-TTS voice playback for AI player speeches. When an AI player finishes speaking (`speech_completed` SSE event), the frontend fetches TTS audio from the backend and plays it through the Web Audio API.

**Architecture:** Backend gets a new `/games/{id}/tts` POST endpoint that accepts `{ text, voice }` and returns MP3 audio bytes via edge-tts. Frontend adds three new modules: `AudioQueue` (manages play order + interruption), `StreamPlayer` (Web Audio API decode + play), `tts` service (API client). A new `useTtsPlayback` hook in App.tsx listens for `speech_completed` events from the store and triggers TTS fetch → play.

**Tech Stack:** edge-tts (Python, backend), Web Audio API (browser, no extra library), zustand ^5.x (Phase 1a pre-req), framer-motion ^11.x (Phase 1b pre-req)

**MVP simplification:** Speech-level TTS (not sentence-level streaming). When an AI player finishes speaking, play their full speech as audio. Streaming TTS (sentence-level chunking) is deferred to Phase 2.

**Pre-requisites:** Phase 1a (Zustand), Phase 1b (Framer Motion).

**What does NOT change (scope boundary):**
- GameTable.tsx — zero changes (audio plays independently, no UI changes needed)
- PhaseSceneRouter.tsx — zero changes
- LobbyPage.tsx — zero changes
- Admin pages — zero changes
- gameStore.ts — zero changes (we add new stores, don't modify existing)
- types.ts — zero changes (TTS types are internal to new modules)
- styles.css — zero changes
- All existing tests pass unchanged

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `ai_werewolf/api/games.py` | **Modify** | Add `POST /games/{id}/tts` endpoint |
| `ai_werewolf/pyproject.toml` | **Modify** | Add `edge-tts` dependency |
| `frontend/src/audio/StreamPlayer.ts` | **Create** | Web Audio API: decode MP3, play, track progress |
| `frontend/src/audio/AudioQueue.ts` | **Create** | Queue management: enqueue, interrupt, flush |
| `frontend/src/services/tts.ts` | **Create** | TTS API client: fetch audio for text |
| `frontend/src/hooks/useTtsPlayback.ts` | **Create** | React hook: wire speech_completed → TTS → audio |
| `frontend/src/App.tsx` | **Modify** | Add `useTtsPlayback` hook to GameRoute |

---

### Task 1: Add backend TTS endpoint with edge-tts

**Files:**
- Modify: `ai_werewolf/pyproject.toml` (add edge-tts dep)
- Modify: `ai_werewolf/api/games.py` (add POST /games/{id}/tts)

- [ ] **Step 1: Install edge-tts**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf
.venv/bin/pip install edge-tts
```

Then update `pyproject.toml` to include the dependency (under `[project]` → `dependencies`):
```toml
dependencies = [
    "fastapi>=0.136.1",
    "edge-tts>=6.1",
]
```

- [ ] **Step 2: Add TTS endpoint to games.py**

Add the import at the top of `ai_werewolf/api/games.py`:

```python
import io
import edge_tts
from fastapi.responses import Response
```

Add the new route after `submit_action` (before `stream_game`):

```python
@app.post("/games/{game_id}/tts")
async def tts_speech(game_id: str, request: Request):
    """
    Generate TTS audio for a speech segment.
    Body: { "text": "...", "voice": "zh-CN-XiaoxiaoNeural" }
    Returns: audio/mpeg binary
    """
    body = await request.json()
    text = body.get("text", "").strip()
    voice = body.get("voice", "zh-CN-XiaoxiaoNeural")

    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    communicate = edge_tts.Communicate(text, voice)
    audio_buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])

    audio_buffer.seek(0)
    return Response(
        content=audio_buffer.getvalue(),
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline"}
    )
```

The `app` object is already created in `api/games.py` since it uses `app = APIRouter()` (wait, I need to check — the explore agent said games_router). Let me verify:

Actually from the explore results: `app.include_router(games_router)`. So the routes in `api/games.py` are on a router, not the app directly. Let me adjust:

```python
from fastapi import APIRouter
router = APIRouter(prefix="/games", tags=["games"])
```

The handler would be:

```python
@router.post("/{game_id}/tts")
async def tts_speech(game_id: str, request: Request):
    body = await request.json()
    text = body.get("text", "").strip()
    voice = body.get("voice", "zh-CN-XiaoxiaoNewNeural")

    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    communicate = edge_tts.Communicate(text, voice)
    audio_buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])

    audio_buffer.seek(0)
    return Response(
        content=audio_buffer.getvalue(),
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline"}
    )
```

(Rest of the API file uses `router` not `app`.)

- [ ] **Step 3: Test the endpoint manually**

Start the backend (if not running):
```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
```

Test with curl:
```bash
curl -X POST http://127.0.0.1:8000/games/test-tts/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "我觉得3号玩家非常可疑", "voice": "zh-CN-XiaoxiaoNeural"}' \
  -o /tmp/test_tts.mp3
file /tmp/test_tts.mp3
```

Expected: `file` reports "MPEG ADTS, layer III" or similar audio format. The file plays audible Chinese speech.

- [ ] **Step 4: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add ai_werewolf/pyproject.toml ai_werewolf/api/games.py
git commit -m "feat(backend): add Edge-TTS endpoint POST /games/{id}/tts"
```

---

### Task 2: Create frontend TTS service client

**Files:**
- Create: `frontend/src/services/tts.ts`

- [ ] **Step 1: Create services directory and tts.ts**

```bash
mkdir -p /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend/src/services
```

Create `frontend/src/services/tts.ts`:

```typescript
import { apiBaseUrl } from "../api";

export interface TtsRequest {
  text: string;
  voice?: string;
}

/**
 * Fetch TTS audio for the given text.
 * Default voice: zh-CN-XiaoxiaoNeural (female, natural Chinese)
 * Returns: ArrayBuffer of MP3 audio data
 */
export async function fetchTtsAudio(
  gameId: string,
  request: TtsRequest,
  baseUrl = apiBaseUrl()
): Promise<ArrayBuffer> {
  const response = await fetch(`${baseUrl}/games/${gameId}/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: request.text,
      voice: request.voice ?? "zh-CN-XiaoxiaoNeural"
    })
  });

  if (!response.ok) {
    throw new Error(`TTS request failed: ${response.status} ${response.statusText}`);
  }

  return response.arrayBuffer();
}

/** Map agent voice preferences to Edge-TTS voice names */
export const VOICE_MAP: Record<string, string> = {
  // Default voices per personality type — overridable per agent
  default: "zh-CN-XiaoxiaoNeural",      // Female, cheerful
  deep: "zh-CN-YunxiNeural",             // Male, deep
  bright: "zh-CN-XiaoyiNeural",          // Female, bright
  calm: "zh-CN-YunjianNeural",           // Male, calm
  gentle: "zh-CN-XiaochenNeural",        // Female, gentle
};

export function getVoiceForAgent(voicePreference?: string): string {
  return voicePreference && voicePreference in VOICE_MAP
    ? VOICE_MAP[voicePreference]
    : VOICE_MAP.default;
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx tsc --noEmit src/services/tts.ts
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/services/tts.ts
git commit -m "feat(frontend): add TTS service client"
```

---

### Task 3: Create StreamPlayer (Web Audio API wrapper)

**Files:**
- Create: `frontend/src/audio/StreamPlayer.ts`

- [ ] **Step 1: Create audio directory and StreamPlayer.ts**

```bash
mkdir -p /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend/src/audio
```

Create `frontend/src/audio/StreamPlayer.ts`:

```typescript
/**
 * StreamPlayer — decodes and plays audio via Web Audio API.
 *
 * Usage:
 *   const player = new StreamPlayer();
 *   await player.play(audioBuffer); // ArrayBuffer of MP3 data
 *   player.stop();                   // Interrupt playback
 *   player.onEnded = () => { ... };  // Called when playback finishes naturally
 */
export class StreamPlayer {
  private audioContext: AudioContext | null = null;
  private sourceNode: AudioBufferSourceNode | null = null;
  private _onEnded: (() => void) | null = null;

  get isPlaying(): boolean {
    return this.sourceNode !== null;
  }

  set onEnded(callback: (() => void) | null) {
    this._onEnded = callback;
  }

  private ensureContext(): AudioContext {
    if (!this.audioContext) {
      this.audioContext = new AudioContext();
    }
    if (this.audioContext.state === "suspended") {
      this.audioContext.resume();
    }
    return this.audioContext;
  }

  async play(audioData: ArrayBuffer): Promise<void> {
    this.stop(); // Stop any current playback first
    const ctx = this.ensureContext();

    try {
      const audioBuffer = await ctx.decodeAudioData(audioData.slice(0));
      this.sourceNode = ctx.createBufferSource();
      this.sourceNode.buffer = audioBuffer;
      this.sourceNode.connect(ctx.destination);

      this.sourceNode.onended = () => {
        this.sourceNode = null;
        this._onEnded?.();
      };

      this.sourceNode.start(0);
    } catch (error) {
      this.sourceNode = null;
      throw error;
    }
  }

  stop(): void {
    if (this.sourceNode) {
      try {
        this.sourceNode.stop(0);
      } catch {
        // Already stopped — ignore
      }
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
  }

  /** Set playback volume (0.0 to 1.0) */
  setVolume(volume: number): void {
    if (this.audioContext) {
      // Create a gain node if not exists — for simplicity, use a single gain
      const gainNode = (this.audioContext as any).__gainNode;
      if (gainNode) {
        gainNode.gain.value = Math.max(0, Math.min(1, volume));
      }
    }
  }

  destroy(): void {
    this.stop();
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx tsc --noEmit src/audio/StreamPlayer.ts
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/audio/StreamPlayer.ts
git commit -m "feat(frontend): add StreamPlayer for Web Audio API playback"
```

---

### Task 4: Create AudioQueue (playback queue with interruption)

**Files:**
- Create: `frontend/src/audio/AudioQueue.ts`

- [ ] **Step 1: Create AudioQueue.ts**

Create `frontend/src/audio/AudioQueue.ts`:

```typescript
/**
 * AudioQueue — manages sequential audio playback with interruption support.
 *
 * Usage:
 *   const queue = new AudioQueue(player);
 *   queue.enqueue({ playerId: "w1", label: "2号 小明", audioData: arrayBuffer });
 *   queue.enqueue({ playerId: "w2", label: "3号 小王", audioData: arrayBuffer });
 *   // Automatically plays items in order
 *   queue.clear(); // Stop and clear queue
 *   queue.setEnabled(false); // Pause auto-play
 */
import { StreamPlayer } from "./StreamPlayer";

export interface QueueItem {
  playerId: string;
  label: string;
  audioData: ArrayBuffer;
}

export class AudioQueue {
  private player: StreamPlayer;
  private queue: QueueItem[] = [];
  private currentItem: QueueItem | null = null;
  private enabled = true;
  private _onItemStart: ((item: QueueItem) => void) | null = null;
  private _onItemEnd: ((item: QueueItem) => void) | null = null;

  constructor(player: StreamPlayer) {
    this.player = player;
  }

  set onItemStart(callback: ((item: QueueItem) => void) | null) {
    this._onItemStart = callback;
  }

  set onItemEnd(callback: ((item: QueueItem) => void) | null) {
    this._onItemEnd = callback;
  }

  get isPlaying(): boolean {
    return this.player.isPlaying;
  }

  get currentPlayerId(): string | null {
    return this.currentItem?.playerId ?? null;
  }

  enqueue(item: QueueItem): void {
    this.queue.push(item);
    if (this.enabled && this.queue.length === 1 && !this.player.isPlaying) {
      this.playNext();
    }
  }

  /** Stop current playback and clear the queue */
  clear(): void {
    this.player.stop();
    this.queue = [];
    this.currentItem = null;
  }

  /** Pause/resume auto-play (doesn't stop current playback) */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    if (enabled && this.queue.length > 0 && !this.player.isPlaying) {
      this.playNext();
    }
  }

  private playNext(): void {
    const item = this.queue.shift();
    if (!item) {
      this.currentItem = null;
      return;
    }

    this.currentItem = item;
    this._onItemStart?.(item);

    this.player.play(item.audioData).then(() => {
      this._onItemEnd?.(item!);
      this.currentItem = null;
      // Play next in queue (via microtask)
      if (this.enabled) {
        setTimeout(() => this.playNext(), 0);
      }
    }).catch(() => {
      this.currentItem = null;
      if (this.enabled) {
        setTimeout(() => this.playNext(), 0);
      }
    });
  }

  destroy(): void {
    this.clear();
    this._onItemStart = null;
    this._onItemEnd = null;
  }
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx tsc --noEmit src/audio/AudioQueue.ts
```

Expected: No errors (AudioQueue.ts imports StreamPlayer.ts — both must compile together).

- [ ] **Step 3: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/audio/AudioQueue.ts
git commit -m "feat(frontend): add AudioQueue for sequential TTS playback"
```

---

### Task 5: Create useTtsPlayback hook and wire into App.tsx

**Files:**
- Create: `frontend/src/hooks/useTtsPlayback.ts`
- Modify: `frontend/src/App.tsx` (add hook usage in GameRoute)

- [ ] **Step 1: Create hooks directory and useTtsPlayback.ts**

```bash
mkdir -p /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend/src/hooks
```

Create `frontend/src/hooks/useTtsPlayback.ts`:

```typescript
import { useEffect, useRef } from "react";
import { AudioQueue, type QueueItem } from "../audio/AudioQueue";
import { StreamPlayer } from "../audio/StreamPlayer";
import { fetchTtsAudio } from "../services/tts";
import { useGameStore } from "../stores/gameStore";
import type { GameStreamEventDto } from "../types";

/**
 * Hook: listens for speech_completed SSE events, fetches TTS audio,
 * and plays it through the audio queue.
 *
 * Call once in GameRoute — returns nothing, purely side-effect.
 */
export function useTtsPlayback(gameId: string | undefined) {
  const playerRef = useRef<StreamPlayer | null>(null);
  const queueRef = useRef<AudioQueue | null>(null);

  useEffect(() => {
    if (!gameId) return;

    // Initialize audio infrastructure
    const player = new StreamPlayer();
    const queue = new AudioQueue(player);
    playerRef.current = player;
    queueRef.current = queue;

    return () => {
      player.destroy();
      playerRef.current = null;
      queueRef.current = null;
    };
  }, [gameId]);

  // Subscribe to store changes — when a new speech_completed event arrives,
  // fetch TTS and enqueue
  useEffect(() => {
    if (!gameId) return;

    // We need to listen for speech_completed events.
    // The store's applySseEvent removes the streaming speech entry on speech_completed.
    // We watch the store for game.public_events changes to detect new speech_completed events.

    const unsub = useGameStore.subscribe((state, prev) => {
      // Every time the store updates, check if there was a speech_completed
      // by watching the game state for new speech entries in public_events
      const game = state.game;
      const prevGame = prev.game;
      if (!game || !prevGame) return;

      const newEvents = game.public_events.slice(prevGame.public_events.length);
      for (const event of newEvents) {
        if (event.event_type === "speech_completed" && event.payload.message) {
          const speechText = event.payload.message;
          const playerId = event.actor_id;
          if (!speechText || !playerId) continue;

          // Skip human player speeches (no TTS needed)
          const player = game.players.find((p) => p.player_id === playerId);
          if (!player || player.is_human) continue;

          // Fetch and enqueue TTS audio
          fetchTtsAudio(gameId, { text: speechText })
            .then((audioData) => {
              const item: QueueItem = {
                playerId,
                label: `${player.seat}号 ${player.display_name}`,
                audioData
              };
              queueRef.current?.enqueue(item);
            })
            .catch((err) => {
              console.warn("TTS fetch failed, skipping audio:", err);
            });
        }
      }
    });

    return unsub;
  }, [gameId]);
}
```

- [ ] **Step 2: Add the hook to GameRoute in App.tsx**

Add import at the top of App.tsx:
```typescript
import { useTtsPlayback } from "./hooks/useTtsPlayback";
```

Inside `GameRoute()`, add the hook call after the SSE useEffect:

```typescript
// TTS audio playback for AI speeches
useTtsPlayback(gameId);
```

This goes right before the `handleAction` definition (before line 183 in the original, or wherever handleAction is in the migrated version).

- [ ] **Step 3: Verify the app compiles**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx tsc --noEmit
```

Expected: Zero TypeScript errors.

- [ ] **Step 4: Run all existing tests to ensure no regressions**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/frontend
npx vitest run
```

Expected: All tests pass. The `useTtsPlayback` hook is not directly tested in this phase (it requires a running backend with TTS, which is an integration concern). The existing tests don't exercise TTS and should pass unchanged.

- [ ] **Step 5: Commit**

```bash
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
git add frontend/src/hooks/useTtsPlayback.ts frontend/src/App.tsx
git commit -m "feat(frontend): add useTtsPlayback hook to play AI speeches via TTS"
```

---

## Completion Checklist for Phase 1c

- [ ] Backend: `POST /games/{id}/tts` endpoint exists and returns valid MP3 audio
- [ ] Backend: `edge-tts` dependency added to pyproject.toml
- [ ] Frontend: `src/services/tts.ts` TTS client compiles
- [ ] Frontend: `src/audio/StreamPlayer.ts` compiles (Web Audio API wrapper)
- [ ] Frontend: `src/audio/AudioQueue.ts` compiles (playback queue)
- [ ] Frontend: `src/hooks/useTtsPlayback.ts` compiles and is wired into GameRoute
- [ ] App.tsx compiles with zero errors
- [ ] All 7 existing test files pass (zero regressions)
- [ ] Manual test: start game → wait for AI speech → hear TTS audio playback

---

## Next Phase

After Phase 1c is complete, proceed to:
**Phase 1d: Socket.IO Replacement & Backend SSE Enhancements** — Replace `EventSource` SSE with Socket.IO bidirectional communication, enhance SSE event types for TTS/audio, and add reconnection logic.

Plan file: `docs/superpowers/plans/2026-05-16-frontend-phase1d-socketio.md`
