import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AdminAgentsPage } from "./AdminAgentsPage";
import { AdminBoardsPage } from "./AdminBoardsPage";
import { AdminLlmPage } from "./AdminLlmPage";
import { AdminPlayersPage } from "./AdminPlayersPage";

describe("admin pages", () => {
  it("submits player creation only after required fields are present", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    const onRefresh = vi.fn();
    render(<AdminPlayersPage players={[]} onRefresh={onRefresh} onCreate={onCreate} />);

    await userEvent.click(screen.getByRole("button", { name: "新增玩家" }));
    expect(screen.getByText("请先填写玩家名称")).toBeInTheDocument();
    expect(onCreate).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText("玩家名称"), "浏览器测试玩家");
    await userEvent.click(screen.getByRole("button", { name: "新增玩家" }));

    expect(onCreate).toHaveBeenCalledWith({ name: "浏览器测试玩家", is_ai: false });
    expect(onRefresh).toHaveBeenCalledOnce();
  });

  it("shows player creation errors without refreshing", async () => {
    const onCreate = vi.fn().mockRejectedValue(new Error("玩家名称已存在"));
    const onRefresh = vi.fn();
    render(<AdminPlayersPage players={[]} onRefresh={onRefresh} onCreate={onCreate} />);

    await userEvent.type(screen.getByLabelText("玩家名称"), "重复玩家");
    await userEvent.click(screen.getByRole("button", { name: "新增玩家" }));

    expect(await screen.findByText("玩家名称已存在")).toBeInTheDocument();
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("submits board creation only after required fields are present", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    const onRefresh = vi.fn();
    render(<AdminBoardsPage boards={[]} onRefresh={onRefresh} onCreate={onCreate} />);

    await userEvent.click(screen.getByRole("button", { name: "新增板子" }));
    expect(screen.getByText("请先填写板子名称")).toBeInTheDocument();
    expect(onCreate).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText("板子名称"), "浏览器测试板子");
    await userEvent.click(screen.getByRole("button", { name: "新增板子" }));

    expect(onCreate).toHaveBeenCalledWith({
      name: "浏览器测试板子",
      description: null,
      min_players: 6,
      max_players: 6,
      sheriff_enabled: false,
      enabled: true
    });
    expect(onRefresh).toHaveBeenCalledOnce();
  });

  it("shows board creation errors without refreshing", async () => {
    const onCreate = vi.fn().mockRejectedValue(new Error("板子名称已存在"));
    const onRefresh = vi.fn();
    render(<AdminBoardsPage boards={[]} onRefresh={onRefresh} onCreate={onCreate} />);

    await userEvent.type(screen.getByLabelText("板子名称"), "重复板子");
    await userEvent.click(screen.getByRole("button", { name: "新增板子" }));

    expect(await screen.findByText("板子名称已存在")).toBeInTheDocument();
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("submits agent creation only after all required fields are present", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    const onRefresh = vi.fn();
    render(<AdminAgentsPage agents={[]} onRefresh={onRefresh} onCreate={onCreate} />);

    await userEvent.click(screen.getByRole("button", { name: "新增 AI" }));
    expect(screen.getByText("请填写 AI 名称、人格和发言风格")).toBeInTheDocument();
    expect(onCreate).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText("AI 名称"), "浏览器测试AI");
    await userEvent.type(screen.getByLabelText("人格"), "谨慎");
    await userEvent.type(screen.getByLabelText("发言风格"), "短句");
    await userEvent.click(screen.getByRole("button", { name: "新增 AI" }));

    expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({
      name: "浏览器测试AI",
      persona: "谨慎",
      speech_style: "短句"
    }));
    expect(onRefresh).toHaveBeenCalledOnce();
  });

  it("shows agent creation errors without refreshing", async () => {
    const onCreate = vi.fn().mockRejectedValue(new Error("AI 名称已存在"));
    const onRefresh = vi.fn();
    render(<AdminAgentsPage agents={[]} onRefresh={onRefresh} onCreate={onCreate} />);

    await userEvent.type(screen.getByLabelText("AI 名称"), "重复AI");
    await userEvent.type(screen.getByLabelText("人格"), "谨慎");
    await userEvent.type(screen.getByLabelText("发言风格"), "短句");
    await userEvent.click(screen.getByRole("button", { name: "新增 AI" }));

    expect(await screen.findByText("AI 名称已存在")).toBeInTheDocument();
    expect(onRefresh).not.toHaveBeenCalled();
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
      />
    );

    expect(screen.getByText("林野")).toBeInTheDocument();
    expect(screen.getByText("理性")).toBeInTheDocument();
  });

  it("renders board role summary", () => {
    render(
      <AdminBoardsPage
        boards={[
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
        ]}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByText("6人新手局")).toBeInTheDocument();
    expect(screen.getByText("werewolf x2")).toBeInTheDocument();
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
