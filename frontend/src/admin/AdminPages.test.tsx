import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AdminAgentsPage } from "./AdminAgentsPage";
import { AdminBoardsPage } from "./AdminBoardsPage";
import { AdminLlmPage } from "./AdminLlmPage";
import { AdminPlayersPage } from "./AdminPlayersPage";

describe("admin pages", () => {
  it("opens create modal when clicking new player button", async () => {
    const onShowCreate = vi.fn();
    render(
      <AdminPlayersPage
        players={[]}
        onRefresh={vi.fn()}
        onShowCreate={onShowCreate}
        onCreateSubmit={vi.fn()}
      />
    );

    await userEvent.click(screen.getByRole("button", { name: "+ 新建玩家" }));
    expect(onShowCreate).toHaveBeenCalled();
  });

  it("shows empty state with create button", () => {
    const onShowCreate = vi.fn();
    render(
      <AdminPlayersPage
        players={[]}
        onRefresh={vi.fn()}
        onShowCreate={onShowCreate}
        onCreateSubmit={vi.fn()}
      />
    );

    expect(screen.getByText("暂无玩家")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "创建第一个玩家" })).toBeInTheDocument();
  });

  it("opens create modal when clicking new board button", async () => {
    const onShowCreate = vi.fn();
    const onRefresh = vi.fn();
    render(<AdminBoardsPage boards={[]} onRefresh={onRefresh} onShowCreate={onShowCreate} />);

    await userEvent.click(screen.getByRole("button", { name: "+ 新建板子" }));
    expect(onShowCreate).toHaveBeenCalled();
  });

  it("shows create button in empty state", () => {
    const onShowCreate = vi.fn();
    render(<AdminBoardsPage boards={[]} onRefresh={vi.fn()} onShowCreate={onShowCreate} />);

    expect(screen.getByText("暂无板子")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "创建第一个板子" })).toBeInTheDocument();
  });

  it("renders board role summary", () => {
    const boards = [
      {
        board_id: "board_1",
        name: "6人新手局",
        description: "2狼1预3民",
        min_players: 6,
        max_players: 6,
        sheriff_enabled: false,
        enabled: true,
        roles: [{ board_id: "board_1", role_key: "werewolf", count: 2 }]
      }
    ];

    render(<AdminBoardsPage boards={boards} onRefresh={vi.fn()} onShowCreate={vi.fn()} />);

    expect(screen.getByText("6人新手局")).toBeInTheDocument();
    expect(screen.getByText(/werewolf x2/)).toBeInTheDocument();
  });

  it("expands board card to show role editor and actions", async () => {
    const boards = [
      {
        board_id: "board_1",
        name: "6人新手局",
        description: "2狼1预3民",
        min_players: 6,
        max_players: 6,
        sheriff_enabled: false,
        enabled: true,
        roles: [{ board_id: "board_1", role_key: "werewolf", count: 2 }]
      }
    ];

    render(<AdminBoardsPage boards={boards} onRefresh={vi.fn()} onShowCreate={vi.fn()} />);

    await userEvent.click(screen.getByText("6人新手局"));

    expect(screen.getByRole("button", { name: "停用" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "删除" })).toBeInTheDocument();
  });

  it("opens create modal when clicking new agent button", async () => {
    const onShowCreate = vi.fn();
    render(
      <AdminAgentsPage
        agents={[]}
        onRefresh={vi.fn()}
        onShowCreate={onShowCreate}
        onCreateSubmit={vi.fn()}
        onUpdateSubmit={vi.fn()}
      />
    );

    await userEvent.click(screen.getByRole("button", { name: "+ 新建 AI" }));
    expect(onShowCreate).toHaveBeenCalled();
  });

  it("renders agent management table", () => {
    render(
      <AdminAgentsPage
        agents={[
          {
            agent_id: "agent_1",
            name: "林野",
            avatar_url: null,
            avatar_prompt: null,
            enabled: true,
            persona: "理性",
            speech_style: "短句",
            reasoning_level: 4,
            deception_level: 2,
            aggression_level: 2,
            cooperation_level: 4,
            risk_preference: "balanced",
            memory_style: "focus_on_votes",
            default_model_provider_id: "deepseek"
          }
        ]}
        onRefresh={vi.fn()}
        onShowCreate={vi.fn()}
        onCreateSubmit={vi.fn()}
        onUpdateSubmit={vi.fn()}
      />
    );

    expect(screen.getByText("林野")).toBeInTheDocument();
    expect(screen.getByText("理性")).toBeInTheDocument();
    expect(screen.getByText("均衡")).toBeInTheDocument();
  });

  it("renders editable LLM provider and role binding controls", () => {
    render(
      <AdminLlmPage
        providers={[
          {
            provider_id: "deepseek",
            provider_type: "openai_compatible",
            model_name: "deepseek-chat",
            base_url: "https://api.deepseek.com/v1",
            api_key_env: "DEEPSEEK_API_KEY",
            temperature: 0.8,
            max_tokens: 1024,
            timeout: 30
          }
        ]}
        bindings={[{ role_key: "werewolf", provider_id: "deepseek" }]}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getAllByText("deepseek").length).toBeGreaterThan(0);
    expect(screen.getByText("werewolf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "新增 Provider" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存绑定" })).toBeInTheDocument();
  });
});
