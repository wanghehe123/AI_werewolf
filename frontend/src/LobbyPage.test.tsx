import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { LobbyPage } from "./LobbyPage";
import type { AgentProfile, BoardConfig } from "./types";

const board: BoardConfig = {
  board_id: "board_6_beginner",
  name: "6人新手局",
  roles: [
    { role_key: "werewolf", count: 2 },
    { role_key: "seer", count: 1 },
    { role_key: "villager", count: 3 }
  ],
  sheriff_enabled: false,
  speech_rule: "seat_order",
  vote_rule: "single_vote",
  win_condition: "wolves_eliminated_or_parity",
  enabled: true,
  player_count: 6
};

const agents: AgentProfile[] = Array.from({ length: 5 }, (_, index) => ({
  agent_id: `agent_${index}`,
  name: `AI玩家${index + 1}`,
  avatar_url: null,
  avatar_prompt: null,
  persona: "谨慎",
  speech_style: "短句",
  reasoning_level: 3,
  deception_level: 3,
  aggression_level: 2,
  cooperation_level: 4,
  risk_preference: "balanced",
  memory_style: "focus",
  enabled: true
}));

describe("LobbyPage", () => {
  it("renders boards and agents, then creates a game with the selected ids", async () => {
    const createGame = vi.fn().mockResolvedValue({ game_id: "game_123" });

    render(
      <MemoryRouter>
        <LobbyPage boards={boardsWithPlayerCount()} agents={agents} createGame={createGame} />
      </MemoryRouter>
    );

    expect(screen.getAllByText("6人新手局")).toHaveLength(2);
    expect(screen.getByText("AI玩家1")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("玩家名称"), "阿愿");
    await userEvent.click(screen.getByRole("button", { name: "开局" }));

    expect(createGame).toHaveBeenCalledWith({
      board_id: "board_6_beginner",
      human_player_id: expect.stringMatching(/^player_/),
      human_player_name: "阿愿",
      human_role_key: "random",
      agent_ids: ["agent_0", "agent_1", "agent_2", "agent_3", "agent_4"]
    });
    expect(createGame.mock.calls[0][0].human_player_id).not.toBe("human");
  });

  it("lets the player choose a role before creating a game", async () => {
    const createGame = vi.fn().mockResolvedValue({ game_id: "game_123" });

    render(
      <MemoryRouter>
        <LobbyPage boards={boardsWithPlayerCount()} agents={agents} createGame={createGame} />
      </MemoryRouter>
    );

    await userEvent.type(screen.getByLabelText("玩家名称"), "阿愿");
    await userEvent.selectOptions(screen.getByLabelText("选择你的职业"), "seer");
    await userEvent.click(screen.getByRole("button", { name: "开局" }));

    expect(createGame).toHaveBeenCalledWith(expect.objectContaining({
      human_player_name: "阿愿",
      human_role_key: "seer"
    }));
  });

  it("requires a player name before creating a game", async () => {
    const createGame = vi.fn().mockResolvedValue({ game_id: "game_123" });

    render(
      <MemoryRouter>
        <LobbyPage boards={boardsWithPlayerCount()} agents={agents} createGame={createGame} />
      </MemoryRouter>
    );

    expect(screen.getByRole("button", { name: "开局" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("玩家名称"), "阿愿");
    expect(screen.getByRole("button", { name: "开局" })).toBeEnabled();
  });

  it("disables start when selected agents do not fill the board", () => {
    render(
      <MemoryRouter>
        <LobbyPage boards={boardsWithPlayerCount()} agents={agents.slice(0, 4)} createGame={vi.fn()} />
      </MemoryRouter>
    );

    expect(screen.getByRole("button", { name: "开局" })).toBeDisabled();
    expect(screen.getByText("需要选择 5 位 AI 玩家")).toBeInTheDocument();
  });
});

function boardsWithPlayerCount(): BoardConfig[] {
  return [board];
}
