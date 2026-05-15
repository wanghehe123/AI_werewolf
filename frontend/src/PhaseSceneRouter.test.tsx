import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PhaseSceneRouter } from "./PhaseSceneRouter";
import type { GameStateDto } from "./types";

const phases: Array<[GameStateDto["phase"], string]> = [
  ["setup", "准备开局"],
  ["night", "夜晚行动"],
  ["day_announcement", "昨夜信息"],
  ["day_speech", "白天发言"],
  ["exile_vote", "放逐投票"],
  ["last_words", "遗言"],
  ["game_over", "游戏复盘"]
];

describe("PhaseSceneRouter", () => {
  it.each(phases)("renders scene for %s", (phase, title) => {
    render(<PhaseSceneRouter game={mockGame(phase)} onSubmitAction={async () => undefined} pending={false} />);

    expect(screen.getByText(title)).toBeInTheDocument();
  });

  it("renders night target options and submits the selected role action", async () => {
    const submitAction = vi.fn().mockResolvedValue(undefined);
    render(<PhaseSceneRouter game={mockGame("night", "seer_check")} onSubmitAction={submitAction} pending={false} />);

    await userEvent.click(screen.getByLabelText("2号 小明"));
    await userEvent.click(screen.getByRole("button", { name: "查验玩家" }));

    expect(submitAction).toHaveBeenCalledWith({
      action_type: "seer_check",
      target_player_id: "w1",
    });
  });
});

function mockGame(phase: GameStateDto["phase"], nightActionType?: string): GameStateDto {
  return {
    game_id: "game_1",
    board_id: "board_6_beginner",
    phase,
    day_count: 1,
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
        speaking: phase === "day_speech",
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
    winner: phase === "game_over" ? "villagers" : null,
    public_events: [],
    allowed_actions: nightActionType ? [{
      action_type: nightActionType,
      label: "查验玩家",
      requires_target: true,
      target_options: [{ player_id: "w1", label: "2号 小明" }]
    }] : []
  };
}
