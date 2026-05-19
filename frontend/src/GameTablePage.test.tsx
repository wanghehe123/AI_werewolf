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
    expect(screen.getByText("1号")).toBeInTheDocument();
    expect(screen.getAllByText("房间已创建").length).toBeGreaterThanOrEqual(1);

    await userEvent.click(screen.getByRole("button", { name: "开始游戏" }));

    expect(submitAction).toHaveBeenCalledWith({ action_type: "start_game" });
  });

  it("disables action buttons while a request is pending", () => {
    render(<GameTable game={mockGame()} onSubmitAction={vi.fn()} pending />);

    expect(screen.getByRole("button", { name: "开始游戏" })).toBeDisabled();
  });

  it("renders streaming speech deltas as a temporary timeline item", () => {
    render(
      <GameTable
        game={mockGame()}
        onSubmitAction={vi.fn()}
        pending={false}
        streamingSpeeches={{
          agent_xiaoming: {
            label: "2号 小明",
            speech: "我正在实时发言"
          }
        }}
      />
    );

    expect(screen.getByText("实时发言")).toBeInTheDocument();
    expect(screen.getByText("2号 小明：")).toBeInTheDocument();
    expect(screen.getByText("我正在实时发言")).toBeInTheDocument();
  });

  it("renders sheriff election actions and submits the correct choice", async () => {
    const submitAction = vi.fn().mockResolvedValue(undefined);

    render(
      <GameTable
        game={mockGame({
          phase: "sheriff_election",
          allowed_actions: [
            { action_type: "run_for_sheriff", label: "参加竞选" },
            { action_type: "skip_election", label: "不参加" },
          ],
        })}
        onSubmitAction={submitAction}
        pending={false}
      />
    );

    expect(screen.getByRole("heading", { name: "警长竞选", level: 1 })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "参加竞选" }));

    expect(submitAction).toHaveBeenCalledWith({ action_type: "run_for_sheriff" });
  });

  it("renders sheriff vote flow with candidate-only target selection", async () => {
    const submitAction = vi.fn().mockResolvedValue(undefined);
    render(
      <GameTable
        game={mockGame({
          phase: "sheriff_speech",
          players: [
            mockPlayer({ player_id: "human", seat: 1, display_name: "你", is_human: true }),
            mockPlayer({ player_id: "candidate_1", seat: 2, display_name: "小明", sheriff: false }),
            mockPlayer({ player_id: "candidate_2", seat: 3, display_name: "小红", sheriff: false }),
            mockPlayer({ player_id: "bystander", seat: 4, display_name: "小刚", sheriff: false }),
          ],
          allowed_actions: [
            {
              action_type: "vote",
              label: "投票选警长",
              requires_target: true,
              target_options: [
                { player_id: "candidate_1", label: "2号 小明" },
                { player_id: "candidate_2", label: "3号 小红" },
              ],
            },
            { action_type: "abstain", label: "弃票" },
          ],
        })}
        onSubmitAction={submitAction}
        pending={false}
      />
    );

    expect(screen.getByRole("heading", { name: "竞选发言", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("警长投票")).toBeInTheDocument();
    await userEvent.click(screen.getByText("2号"));
    await userEvent.click(screen.getByRole("button", { name: "投给他" }));

    expect(submitAction).toHaveBeenCalledWith({ action_type: "vote", target_player_id: "candidate_1" });
  });
});

function mockPlayer(overrides: Partial<GameStateDto["players"][number]> = {}): GameStateDto["players"][number] {
  return {
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
    voted: false,
    ...overrides,
  };
}

function mockGame(overrides: Partial<GameStateDto> = {}): GameStateDto {
  return {
    game_id: "game_1",
    board_id: "board_6_beginner",
    phase: "setup",
    day_count: 0,
    human_player_id: "human",
    current_turn_player_id: "human",
    players: [mockPlayer()],
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
    allowed_actions: [{ action_type: "start_game", label: "开始游戏" }],
    ...overrides,
  };
}
