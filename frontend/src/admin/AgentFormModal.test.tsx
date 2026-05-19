import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AdminAgentDto } from "../types";
import { AgentFormModal } from "./AgentFormModal";

describe("AgentFormModal", () => {
  const basicProps = {
    isOpen: true,
    onClose: vi.fn(),
    onSubmit: vi.fn().mockResolvedValue({} as AdminAgentDto),
    providers: [{ provider_id: "deepseek", name: "DeepSeek" }],
  };

  it("renders form fields when open", () => {
    render(<AgentFormModal {...basicProps} />);

    expect(screen.getByLabelText("AI 名称")).toBeInTheDocument();
    expect(screen.getByLabelText("人格")).toBeInTheDocument();
    expect(screen.getByLabelText("发言风格")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消" })).toBeInTheDocument();
  });

  it("does not render when closed", () => {
    render(<AgentFormModal {...basicProps} isOpen={false} />);
    expect(screen.queryByLabelText("AI 名称")).not.toBeInTheDocument();
  });

  it("prefills fields in edit mode", () => {
    render(
      <AgentFormModal
        {...basicProps}
        initialValues={{
          agent_id: "a1",
          name: "林野",
          avatar_url: null,
          avatar_prompt: null,
          persona: "理性谨慎",
          speech_style: "短句分析",
          reasoning_level: 5,
          deception_level: 3,
          aggression_level: 2,
          cooperation_level: 4,
          risk_preference: "balanced",
          memory_style: "focus_on_votes",
          default_model_provider_id: null,
          enabled: true,
        }}
      />
    );

    expect(screen.getByDisplayValue("林野")).toBeInTheDocument();
    expect(screen.getByDisplayValue("理性谨慎")).toBeInTheDocument();
    expect(screen.getByDisplayValue("短句分析")).toBeInTheDocument();
  });

  it("submits with all fields", async () => {
    const onSubmit = vi.fn().mockResolvedValue({} as AdminAgentDto);
    render(<AgentFormModal {...basicProps} onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText("AI 名称"), "新AI");
    await userEvent.type(screen.getByLabelText("人格"), "聪明");
    await userEvent.type(screen.getByLabelText("发言风格"), "简洁");
    await userEvent.click(screen.getByRole("button", { name: "确认" }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      name: "新AI",
      persona: "聪明",
      speech_style: "简洁",
      reasoning_level: 3,
      deception_level: 3,
      aggression_level: 3,
      cooperation_level: 3,
      risk_preference: "balanced",
      memory_style: "focus_on_votes",
      enabled: true,
    }));
  });

  it("shows error when submitting empty name", async () => {
    render(<AgentFormModal {...basicProps} />);

    await userEvent.click(screen.getByRole("button", { name: "确认" }));
    expect(screen.getByText(/请填写 AI 名称/)).toBeInTheDocument();
  });

  it("shows error on submit failure", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error("名称已存在"));
    render(<AgentFormModal {...basicProps} onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText("AI 名称"), "重复AI");
    await userEvent.type(screen.getByLabelText("人格"), "聪明");
    await userEvent.type(screen.getByLabelText("发言风格"), "简洁");
    await userEvent.click(screen.getByRole("button", { name: "确认" }));

    expect(await screen.findByText("名称已存在")).toBeInTheDocument();
  });
});
