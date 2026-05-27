import { beforeEach, describe, expect, it, vi } from "vitest";
import { useGameStore } from "./gameStore";
import type { GameStateDto, GameStreamEventDto, StateSnapshotPayload, SpeechDeltaPayload } from "../types";

describe("gameStore", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.unstubAllGlobals();
    useGameStore.getState().reset();
  });

  describe("initial state", () => {
    it("has null game, empty collections, no error", () => {
      const state = useGameStore.getState();
      expect(state.game).toBeNull();
      expect(state.streamingSpeeches).toEqual({});
      expect(state.seerResults).toEqual({});
      expect(state.audioAnnouncements).toEqual([]);
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
      } as unknown as Record<string, unknown>);

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
      });

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
      }));
      useGameStore.getState().applySseEvent(mockSseEvent("speech_delta", {
        player_id: "w1", label: "2号", delta: "B", speech: "第二句"
      }));

      expect(useGameStore.getState().streamingSpeeches["w1"]?.speech).toBe("第二句");
    });
  });

  describe("applySseEvent: speech_completed", () => {
    it("removes streaming speech entry", () => {
      useGameStore.getState().setGame(mockGame());
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
        targetLabel: "2号 小明",
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

    it("queues public system events for audio narration", () => {
      useGameStore.getState().setGame(mockGame("night"));

      useGameStore.getState().applySseEvent(mockSseEvent("night_step_started", {
        message: "狼人开始行动。"
      }));

      expect(useGameStore.getState().audioAnnouncements).toEqual([
        {
          id: expect.stringContaining("evt_"),
          kind: "system",
          text: "狼人开始行动。"
        }
      ]);
    });

    it("queues completed player speeches for audio playback", () => {
      useGameStore.getState().setGame(mockGame("day_speech"));

      useGameStore.getState().applySseEvent({
        ...mockSseEvent("speech_completed", {
          message: "2号 小明：我觉得今天要听逻辑。",
          player_id: "w1",
          label: "2号 小明",
          speech: "我觉得今天要听逻辑。"
        }),
        actor_id: "w1"
      });

      expect(useGameStore.getState().audioAnnouncements.at(-1)).toEqual({
        id: expect.any(String),
        kind: "speech",
        text: "我觉得今天要听逻辑。",
        actorId: "w1",
        label: "2号 小明"
      });
    });

    it("adds completed player speeches to the public timeline immediately", () => {
      useGameStore.getState().setGame(mockGame("day_speech"));

      useGameStore.getState().applySseEvent({
        ...mockSseEvent("speech_completed", {
          message: "2号 小明：我觉得今天要听逻辑。",
          player_id: "w1",
          label: "2号 小明",
          speech: "我觉得今天要听逻辑。"
        }),
        actor_id: "w1",
        phase: "day_speech",
        day_count: 1
      });

      const event = useGameStore.getState().game?.public_events.at(-1);
      expect(event).toMatchObject({
        event_type: "speech_completed",
        actor_id: "w1",
        target_id: null,
        payload: { message: "2号 小明：我觉得今天要听逻辑。" },
        public: true
      });
    });

    it("marks the current speaker from current_speaker_changed events", () => {
      useGameStore.getState().setGame(mockGame("sheriff_speech"));

      useGameStore.getState().applySseEvent({
        ...mockSseEvent("current_speaker_changed", {
          player_id: "w1",
          label: "2号 小明"
        }),
        actor_id: "w1",
        phase: "sheriff_speech"
      });

      const game = useGameStore.getState().game!;
      expect(game.players.find((p) => p.player_id === "w1")?.speaking).toBe(true);
    });

    it("adds sheriff election and vote stream events to the timeline immediately", () => {
      useGameStore.getState().setGame(mockGame("sheriff_election"));

      useGameStore.getState().applySseEvent({
        ...mockSseEvent("sheriff_election", { message: "2号 小明 参加警长竞选。" }),
        actor_id: "w1",
        phase: "sheriff_election"
      });
      useGameStore.getState().applySseEvent({
        ...mockSseEvent("sheriff_election_speech", {
          message: "2号 小明：我竞选警长。",
          player_id: "w1",
          label: "2号 小明",
          speech: "我竞选警长。"
        }),
        actor_id: "w1",
        phase: "sheriff_speech"
      });
      useGameStore.getState().applySseEvent({
        ...mockSseEvent("sheriff_vote", { message: "1号 你 投票给 2号 小明。" }),
        actor_id: "human",
        target_id: "w1",
        phase: "sheriff_speech"
      });

      const events = useGameStore.getState().game!.public_events;
      expect(events.map((event) => event.event_type).slice(-3)).toEqual([
        "sheriff_election",
        "sheriff_election_speech",
        "sheriff_vote"
      ]);
      expect(events.at(-1)?.target_id).toBe("w1");
    });

    it("adds exile vote stream events to the timeline immediately", () => {
      useGameStore.getState().setGame(mockGame("exile_vote"));

      useGameStore.getState().applySseEvent({
        ...mockSseEvent("vote", { message: "2号 小明 选择弃票。" }),
        actor_id: "w1",
        phase: "exile_vote"
      });

      const event = useGameStore.getState().game!.public_events.at(-1);
      expect(event).toMatchObject({
        event_type: "vote",
        actor_id: "w1",
        target_id: null,
        payload: { message: "2号 小明 选择弃票。" },
        public: true
      });
    });

    it("does not queue private info for public audio narration", () => {
      useGameStore.getState().setGame(mockGame("night"));
      const seerEvent = mockSseEvent("private_info", { message: "你的查验结果：2号 是狼人阵营。" });
      seerEvent.visibility = "self";
      seerEvent.target_id = "w1";

      useGameStore.getState().applySseEvent(seerEvent);

      expect(useGameStore.getState().audioAnnouncements).toEqual([]);
    });
  });

  describe("submitAction", () => {
    it("sets pending true during submission", () => {
      expect(useGameStore.getState().pending).toBe(false);
      useGameStore.setState({ pending: true });
      expect(useGameStore.getState().pending).toBe(true);
    });

    it("uses the loaded human player id when submitting actions", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ code: 0, data: { ...mockGame(), human_player_id: "player_abc" } })
      });
      vi.stubGlobal("fetch", fetchMock);
      useGameStore.getState().setGame({ ...mockGame(), human_player_id: "player_abc" });

      await useGameStore.getState().submitAction("game_1", { action_type: "start_game" });

      const [, init] = fetchMock.mock.calls[0];
      expect(JSON.parse(init.body)).toMatchObject({ actor_player_id: "player_abc" });
    });

    it("restores a remembered room token after reset and sends it on the first action", async () => {
      const fetchMock = vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ code: 0, data: { ...mockGame(), game_id: "game_1" } })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ code: 0, data: { ...mockGame(), game_id: "game_1" } })
        });
      vi.stubGlobal("fetch", fetchMock);

      useGameStore.getState().rememberRoomToken("game_1", "room-token-123");
      useGameStore.getState().reset();

      await useGameStore.getState().loadGame("game_1");
      await useGameStore.getState().submitAction("game_1", { action_type: "start_game" });

      const [, submitInit] = fetchMock.mock.calls[1];
      expect(submitInit.headers).toMatchObject({ "X-Room-Token": "room-token-123" });
    });
  });

  describe("reset", () => {
    it("returns all state to initial values", () => {
      useGameStore.getState().setGame(mockGame());
      useGameStore.setState({
        streamingSpeeches: { w1: { label: "2号", speech: "test" } },
        seerResults: { w1: { targetPlayerId: "w1", targetLabel: "2号", camp: "good" } },
        audioAnnouncements: [{ id: "evt_1", kind: "system", text: "测试播报" }],
        pending: true,
        error: "some error"
      });

      useGameStore.getState().reset();

      const state = useGameStore.getState();
      expect(state.game).toBeNull();
      expect(state.streamingSpeeches).toEqual({});
      expect(state.seerResults).toEqual({});
      expect(state.audioAnnouncements).toEqual([]);
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
