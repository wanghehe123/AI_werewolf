import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PhaseSceneRouter } from "./PhaseSceneRouter";
import type { GameStateDto } from "./types";

const phases: Array<[GameStateDto["phase"], string]> = [
  ["setup", "准备开局"],
  ["night", "夜晚行动"],
  ["day_announcement", "昨夜信息"],
  ["day_speech", "白天发言"],
  ["day_vote", "放逐投票"],
  ["game_over", "游戏复盘"]
];

describe("PhaseSceneRouter", () => {
  it.each(phases)("renders scene for %s", (phase, title) => {
    render(<PhaseSceneRouter game={mockGame(phase)} onSubmitAction={async () => undefined} pending={false} />);

    expect(screen.getByText(title)).toBeInTheDocument();
  });
});

function mockGame(phase: GameStateDto["phase"]): GameStateDto {
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
      }
    ],
    winner: phase === "game_over" ? "villagers" : null,
    public_events: [],
    allowed_actions: []
  };
}
