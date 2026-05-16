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
  setGame: (game: GameStateDto | null) => void;
  setPending: (pending: boolean) => void;
  setError: (error: string | null) => void;
  applySseEvent: (event: GameStreamEventDto) => void;
  appendStreamEvent: (event: GameStreamEventDto) => void;
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
    pending: false,
    error: null
  };
}

export const useGameStore = create<GameStore>((set, get) => ({
  ...initialState(),

  setGame: (game) => set({ game, error: null }),

  setPending: (pending) => set({ pending }),

  setError: (error) => set({ error }),

  applySseEvent: (event) => {
    const currentGame = get().game;

    if (event.event_type === "state_snapshot") {
      const payload = event.payload as unknown as StateSnapshotPayload;
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
      return;
    }

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
