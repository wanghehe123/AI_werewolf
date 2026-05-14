import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { GameTable } from "./GameTable";
import type { GameStateDto } from "./types";

describe("GameTable", () => {
  it("renders the phase, seats, events, and submits the setup action", async () => {
    const submitAction = vi.fn().mockResolvedValue(undefined);

    render(<GameTable game={mockGame()} onSubmitAction={submitAction} pending={false} />);

    expect(screen.getByRole("heading", { name: "准备开局", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("1号位")).toBeInTheDocument();
    expect(screen.getByText("房间已创建")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "开始游戏" }));

    expect(submitAction).toHaveBeenCalledWith({ action_type: "start_game" });
  });

  it("disables action buttons while a request is pending", () => {
    render(<GameTable game={mockGame()} onSubmitAction={vi.fn()} pending />);

    expect(screen.getByRole("button", { name: "开始游戏" })).toBeDisabled();
  });
});

function mockGame(): GameStateDto {
  return {
    game_id: "game_1",
    board_id: "board_6_beginner",
    phase: "setup",
    day_count: 0,
    human_player_id: "human",
    current_turn_player_id: "human",
    players: [
      {
        player_id: "human",
        agent_id: null,
        seat: 1,
        role_key: "villager",
        alive: true,
        is_human: true,
        sheriff: false,
        display_name: "你",
        avatar_url: null,
        speaking: false,
        voted: false
      }
    ],
    winner: null,
    public_events: [
      {
        event_type: "game_created",
        actor_id: null,
        target_id: null,
        payload: { message: "房间已创建" },
        public: true
      }
    ],
    allowed_actions: [{ action_type: "start_game", label: "开始游戏" }]
  };
}
