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
    expect(screen.getAllByText("警长投票").length).toBeGreaterThanOrEqual(1);
    await userEvent.click(screen.getByText("2号"));
    await userEvent.click(screen.getByRole("button", { name: "投给他" }));

    expect(submitAction).toHaveBeenCalledWith({ action_type: "vote", target_player_id: "candidate_1" });
  });

  it("renders a new exile vote tally even when an older exile event exists", () => {
    render(
      <GameTable
        game={mockGame({
          phase: "exile_vote",
          players: [
            mockPlayer({ player_id: "human", seat: 1, display_name: "你", is_human: true }),
            mockPlayer({ player_id: "candidate_1", seat: 2, display_name: "小明" }),
            mockPlayer({ player_id: "candidate_2", seat: 3, display_name: "小红" }),
          ],
          public_events: [
            { event_type: "exile", actor_id: null, target_id: "candidate_2", payload: { message: "上一轮小红被放逐。" }, public: true },
            { event_type: "phase_changed", actor_id: null, target_id: null, payload: { message: "发言结束，进入放逐投票。" }, public: true },
            { event_type: "vote", actor_id: "candidate_1", target_id: "candidate_2", payload: { message: "2号 小明 投票给 3号 小红。" }, public: true },
          ],
          allowed_actions: [],
        })}
        onSubmitAction={vi.fn()}
        pending={false}
      />
    );

    expect(screen.getAllByText("放逐投票").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("已投 1 票")).toBeInTheDocument();
    expect(screen.getByText("3号 小红")).toBeInTheDocument();
  });

  it("counts abstentions as voted in the sheriff tally pending list", () => {
    render(
      <GameTable
        game={mockGame({
          phase: "sheriff_speech",
          players: [
            mockPlayer({ player_id: "human", seat: 1, display_name: "你", is_human: true }),
            mockPlayer({ player_id: "candidate_1", seat: 2, display_name: "小明" }),
            mockPlayer({ player_id: "candidate_2", seat: 3, display_name: "小红" }),
            mockPlayer({ player_id: "bystander", seat: 4, display_name: "小刚" }),
          ],
          public_events: [
            { event_type: "sheriff_election", actor_id: "candidate_1", target_id: null, payload: { message: "2号 小明 参加警长竞选。" }, public: true },
            { event_type: "sheriff_election", actor_id: "candidate_2", target_id: null, payload: { message: "3号 小红 参加警长竞选。" }, public: true },
            { event_type: "phase_changed", actor_id: null, target_id: null, payload: { message: "竞选发言结束，请非候选玩家投票选出警长。" }, public: true },
            { event_type: "sheriff_vote", actor_id: "bystander", target_id: null, payload: { message: "4号 小刚 弃票。" }, public: true },
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
          ],
        })}
        onSubmitAction={vi.fn()}
        pending={false}
      />
    );

    expect(screen.getAllByText("警长投票").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("已投 1 票")).toBeInTheDocument();
    expect(screen.queryByText(/待投票：.*小刚/)).not.toBeInTheDocument();
  });

  it("clears sheriff candidate markers after the sheriff election result", () => {
    render(
      <GameTable
        game={mockGame({
          phase: "day_announcement",
          players: [
            mockPlayer({ player_id: "human", seat: 1, display_name: "你", is_human: true }),
            mockPlayer({ player_id: "candidate_1", seat: 2, display_name: "小明", sheriff: true }),
            mockPlayer({ player_id: "candidate_2", seat: 3, display_name: "小红", sheriff: false }),
          ],
          public_events: [
            { event_type: "sheriff_election", actor_id: "candidate_1", target_id: null, payload: { message: "2号 小明 参加警长竞选。" }, public: true },
            { event_type: "sheriff_election", actor_id: "candidate_2", target_id: null, payload: { message: "3号 小红 参加警长竞选。" }, public: true },
            { event_type: "sheriff_elected", actor_id: "candidate_1", target_id: null, payload: { message: "2号 小明 当选警长。" }, public: true },
          ],
          allowed_actions: [],
        })}
        onSubmitAction={vi.fn()}
        pending={false}
      />
    );

    expect(screen.queryAllByAltText("举手参选")).toHaveLength(0);
    expect(screen.queryByText("参选")).not.toBeInTheDocument();
    expect(screen.getByText("警长")).toBeInTheDocument();
  });

  it("keeps a long center event in its own scroll region", () => {
    const longSpeech = "8号 李向左：".repeat(80);

    render(
      <GameTable
        game={mockGame({
          phase: "sheriff_speech",
          players: [
            mockPlayer({ player_id: "human", seat: 1, display_name: "你", is_human: true }),
            mockPlayer({ player_id: "candidate_1", seat: 2, display_name: "小明" }),
            mockPlayer({ player_id: "candidate_2", seat: 3, display_name: "小红" }),
            mockPlayer({ player_id: "bystander", seat: 4, display_name: "小刚" }),
          ],
          public_events: [
            { event_type: "sheriff_election_speech", actor_id: "candidate_1", target_id: null, payload: { message: longSpeech }, public: true },
          ],
          allowed_actions: [{ action_type: "speech", label: "发言" }],
        })}
        onSubmitAction={vi.fn()}
        pending={false}
      />
    );

    expect(screen.getByLabelText("游戏桌面区域").className).toContain("overflow-hidden");
    expect(screen.getByLabelText("当前事件摘要").className).toContain("overflow-y-auto");
    expect(screen.getByLabelText("发言内容")).toBeInTheDocument();
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
