import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, createGame, fetchBoards, submitGameAction, subscribeGameStream } from "./api";

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses the configured base url when fetching boards", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ board_id: "board_6_beginner" }]
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchBoards("http://api.local");

    expect(fetchMock).toHaveBeenCalledWith("http://api.local/boards", undefined);
  });

  it("throws ApiError for failed backend responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: "agent count must match" })
      })
    );

    await expect(
      createGame({ board_id: "board_6_beginner", human_player_id: "human", agent_ids: [] }, "http://api.local")
    ).rejects.toMatchObject(new ApiError(400, "agent count must match"));
  });

  it("subscribes to the game SSE stream with the player id", () => {
    const addEventListener = vi.fn();
    const close = vi.fn();
    const eventSourceMock = vi.fn().mockImplementation(function EventSourceMock() {
      return { addEventListener, close };
    });
    vi.stubGlobal("EventSource", eventSourceMock);

    const subscription = subscribeGameStream("game_1", { playerId: "human", onEvent: vi.fn() }, "http://api.local");

    expect(eventSourceMock).toHaveBeenCalledWith("http://api.local/games/game_1/stream?player_id=human");
    expect(addEventListener).toHaveBeenCalledWith("state_snapshot", expect.any(Function));
    expect(addEventListener).toHaveBeenCalledWith("speech_delta", expect.any(Function));
    expect(addEventListener).toHaveBeenCalledWith("sheriff_election", expect.any(Function));
    expect(addEventListener).toHaveBeenCalledWith("sheriff_election_speech", expect.any(Function));
    expect(addEventListener).toHaveBeenCalledWith("sheriff_vote", expect.any(Function));
    expect(addEventListener).toHaveBeenCalledWith("vote", expect.any(Function));
    expect(addEventListener).toHaveBeenCalledWith("exile", expect.any(Function));
    subscription.close();
    expect(close).toHaveBeenCalled();
  });

  it("submits actions with the current human player id", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ code: 0, data: { game_id: "game_1" } })
    });
    vi.stubGlobal("fetch", fetchMock);

    await submitGameAction("game_1", { action_type: "start_game" }, "player_abc", "http://api.local");

    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init.body)).toMatchObject({
      actor_player_id: "player_abc",
      action_type: "start_game"
    });
  });
});
