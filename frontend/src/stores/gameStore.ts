import { create } from "zustand";
import { fetchGame, submitGameAction } from "../api";
import type {
  AudioAnnouncement,
  GameStateDto,
  GameEventDto,
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
  audioAnnouncements: AudioAnnouncement[];
  pending: boolean;
  error: string | null;

  // --- Actions ---
  setGame: (game: GameStateDto | null) => void;
  setPending: (pending: boolean) => void;
  setError: (error: string | null) => void;
  applySseEvent: (event: GameStreamEventDto) => void;
  appendStreamEvent: (event: GameStreamEventDto) => void;
  removeAudioAnnouncement: (announcementId: string) => void;
  loadGame: (gameId: string) => Promise<void>;
  submitAction: (gameId: string, action: SubmitActionInput) => Promise<void>;
  clearError: () => void;
  reset: () => void;
}

function initialState() {
  return {
    game: null,
    streamingSpeeches: {},
    seerResults: {},
    audioAnnouncements: [],
    pending: false,
    error: null
  };
}

// Track signatures of public events already announced via SSE, so that
// announcementsFromGameDiff (called from state_snapshot handler) only
// picks up events that have no SSE counterpart (e.g. exile).
let sseAnnouncedSignatures = new Set<string>();

export const useGameStore = create<GameStore>((set, get) => ({
  ...initialState(),

  setGame: (game) => set({ game, error: null }),

  setPending: (pending) => set({ pending }),

  setError: (error) => set({ error }),

  applySseEvent: (event) => {
    const currentGame = get().game;

    if (event.event_type === "state_snapshot") {
      const payload = event.payload as unknown as StateSnapshotPayload;
      const prevGame = currentGame;
      // Generate announcements from new public_events that were NOT
      // already announced via individual SSE events.
      if (prevGame && payload.game_state) {
        const prevLen = prevGame.public_events.length;
        const newPublicEvents = payload.game_state.public_events.slice(prevLen);
        const allNew = announcementsFromGameDiff(prevGame, payload.game_state);
        const remaining = allNew.filter((_, i) => {
          const pe = newPublicEvents[i];
          if (!pe) return false;
          const sig = `${pe.event_type}::${pe.payload.message?.trim() ?? ""}`;
          return !sig || !sseAnnouncedSignatures.has(sig);
        });
        if (remaining.length > 0) {
          set((state) => ({
            game: payload.game_state,
            audioAnnouncements: remaining.reduce(appendAnnouncement, state.audioAnnouncements)
          }));
          return;
        }
      }
      set({ game: payload.game_state });
      return;
    }

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
      get().appendStreamEvent(event);
      return;
    }

    if (event.event_type === "private_info") {
      const payload = event.payload as unknown as PrivateInfoPayload;
      // Witch kill notification — not a seer result, skip seerResult creation.
      // The kill info is already shown in the WitchNightAction component.
      if (payload.subtype === "witch_kill") return;
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

    get().appendStreamEvent(event);
  },

  appendStreamEvent: (event) => {
    const currentGame = get().game;
    if (!currentGame || typeof event.payload.message !== "string") return;

    const announcement = announcementFromSseEvent(event);

    // Record the signature so duplicate public events from state_snapshot
    // are not re-announced.
    if (announcement) {
      const msg = stringPayload(event.payload.message);
      if (msg) {
        sseAnnouncedSignatures.add(`${event.event_type}::${msg}`);
      }
    }

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
      },
      ...(announcement ? { audioAnnouncements: appendAnnouncement(get().audioAnnouncements, announcement) } : {})
    });
  },

  removeAudioAnnouncement: (announcementId) => set((state) => ({
    audioAnnouncements: state.audioAnnouncements.filter((announcement) => announcement.id !== announcementId)
  })),

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
      // Announcements are generated from SSE events, not here.
      // state_snapshot (always the last SSE event) handles
      // public_events that lack an SSE counterpart (e.g. exile).
      set({ game, pending: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "行动失败",
        pending: false
      });
    }
  },

  clearError: () => set({ error: null }),

  reset: () => {
    sseAnnouncedSignatures = new Set();
    set(initialState());
  }
}));

const NARRATABLE_SYSTEM_EVENTS = new Set([
  "phase_changed",
  "night_step_started",
  "night_step_finished",
  "night_result",
  "exile",
  "game_end",
]);

function announcementFromSseEvent(event: GameStreamEventDto): AudioAnnouncement | null {
  if (event.visibility !== "public") return null;

  if (event.event_type === "speech_completed") {
    const text = stringPayload(event.payload.speech) ?? stripSpeakerPrefix(stringPayload(event.payload.message) ?? "");
    if (!text) return null;
    return {
      id: event.event_id,
      kind: "speech",
      text,
      actorId: event.actor_id ?? undefined,
      label: stringPayload(event.payload.label) ?? undefined,
    };
  }

  if (!NARRATABLE_SYSTEM_EVENTS.has(event.event_type)) return null;
  const message = stringPayload(event.payload.message);
  if (!message) return null;
  return {
    id: event.event_id,
    kind: "system",
    text: message,
  };
}

function announcementsFromGameDiff(previousGame: GameStateDto | null, nextGame: GameStateDto): AudioAnnouncement[] {
  const previousLength = previousGame?.public_events.length ?? nextGame.public_events.length;
  return nextGame.public_events
    .slice(previousLength)
    .map((event, offset) => announcementFromPublicEvent(event, previousLength + offset))
    .filter((announcement): announcement is AudioAnnouncement => announcement !== null);
}

function announcementFromPublicEvent(event: GameEventDto, index: number): AudioAnnouncement | null {
  if (!event.public) return null;
  const message = event.payload.message?.trim();
  if (!message) return null;

  if (event.event_type === "speech" || (event.event_type === "last_words" && event.actor_id && message.includes("："))) {
    return {
      id: `public-${index}-${event.event_type}`,
      kind: "speech",
      text: stripSpeakerPrefix(message),
      actorId: event.actor_id ?? undefined,
      label: message.includes("：") ? message.split("：", 1)[0] : undefined,
    };
  }

  if (!NARRATABLE_SYSTEM_EVENTS.has(event.event_type) && event.event_type !== "last_words") return null;
  return {
    id: `public-${index}-${event.event_type}`,
    kind: "system",
    text: message,
  };
}

function appendAnnouncement(announcements: AudioAnnouncement[], announcement: AudioAnnouncement): AudioAnnouncement[] {
  if (announcements.some((item) => item.id === announcement.id)) {
    return announcements;
  }
  return [...announcements, announcement];
}

function stringPayload(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function stripSpeakerPrefix(message: string): string {
  const separatorIndex = message.indexOf("：");
  return separatorIndex >= 0 ? message.slice(separatorIndex + 1).trim() : message.trim();
}
