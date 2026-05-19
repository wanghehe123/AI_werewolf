import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AdminBoardDto, AdminRoleDto } from "../types";
import { BoardCreateModal } from "./BoardCreateModal";

const mockRoles: AdminRoleDto[] = [
  { role_key: "werewolf", name: "狼人", faction: "wolf", description: "夜晚可击杀", night_action: true, enabled: true },
  { role_key: "seer", name: "预言家", faction: "good", description: "夜晚查验身份", night_action: true, enabled: true },
  { role_key: "witch", name: "女巫", faction: "good", description: "解药和毒药", night_action: true, enabled: true },
  { role_key: "hunter", name: "猎人", faction: "good", description: "出局带人", night_action: false, enabled: true },
  { role_key: "villager", name: "平民", faction: "good", description: "无技能", night_action: false, enabled: true },
];

describe("BoardCreateModal", () => {
  it("renders form fields when open", () => {
    render(
      <BoardCreateModal isOpen={true} roles={mockRoles} onCreateComplete={vi.fn()} onClose={vi.fn()} />
    );

    expect(screen.getByLabelText("板子名称")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "创建板子" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消" })).toBeInTheDocument();
  });

  it("does not render when closed", () => {
    render(
      <BoardCreateModal isOpen={false} roles={mockRoles} onCreateComplete={vi.fn()} onClose={vi.fn()} />
    );

    expect(screen.queryByLabelText("板子名称")).not.toBeInTheDocument();
  });

  it("calls onClose when cancel is clicked", async () => {
    const onClose = vi.fn();
    render(
      <BoardCreateModal isOpen={true} roles={mockRoles} onCreateComplete={vi.fn()} onClose={onClose} />
    );

    await userEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("submits with complete payload via createAdminBoardComplete", async () => {
    const onCreateComplete = vi.fn().mockResolvedValue({} as AdminBoardDto);
    render(
      <BoardCreateModal isOpen={true} roles={mockRoles} onCreateComplete={onCreateComplete} onClose={vi.fn()} />
    );

    await userEvent.type(screen.getByLabelText("板子名称"), "8人标准局");
    await userEvent.clear(screen.getByLabelText("人数"));
    await userEvent.type(screen.getByLabelText("人数"), "8");

    // Add 2 werewolves
    const werewolfPlus = screen.getByRole("button", { name: "增加 狼人" });
    await userEvent.click(werewolfPlus);
    await userEvent.click(werewolfPlus);

    // Add 1 seer
    await userEvent.click(screen.getByRole("button", { name: "增加 预言家" }));

    // Add 3 villagers
    const villagerPlus = screen.getByRole("button", { name: "增加 平民" });
    await userEvent.click(villagerPlus);
    await userEvent.click(villagerPlus);
    await userEvent.click(villagerPlus);

    // Add 1 witch
    await userEvent.click(screen.getByRole("button", { name: "增加 女巫" }));

    // Add 1 hunter
    await userEvent.click(screen.getByRole("button", { name: "增加 猎人" }));

    await userEvent.click(screen.getByRole("button", { name: "创建板子" }));

    expect(onCreateComplete).toHaveBeenCalledWith({
      name: "8人标准局",
      description: null,
      min_players: 8,
      max_players: 8,
      sheriff_enabled: true,
      enabled: true,
      roles: [
        { role_key: "werewolf", count: 2 },
        { role_key: "seer", count: 1 },
        { role_key: "villager", count: 3 },
        { role_key: "witch", count: 1 },
        { role_key: "hunter", count: 1 },
      ],
    });
  });

  it("shows error when submitting without name", async () => {
    render(
      <BoardCreateModal isOpen={true} roles={mockRoles} onCreateComplete={vi.fn()} onClose={vi.fn()} />
    );

    await userEvent.click(screen.getByRole("button", { name: "创建板子" }));
    expect(screen.getByText(/请填写板子名称/)).toBeInTheDocument();
  });

  it("shows error message on create failure", async () => {
    const onCreateComplete = vi.fn().mockRejectedValue(new Error("板子名称已存在"));
    render(
      <BoardCreateModal isOpen={true} roles={mockRoles} onCreateComplete={onCreateComplete} onClose={vi.fn()} />
    );

    await userEvent.type(screen.getByLabelText("板子名称"), "重复板子");
    await userEvent.clear(screen.getByLabelText("人数"));
    await userEvent.type(screen.getByLabelText("人数"), "2");
    // Add 1 werewolf + 1 villager to satisfy total >= players check
    await userEvent.click(screen.getByRole("button", { name: "增加 狼人" }));
    await userEvent.click(screen.getByRole("button", { name: "增加 平民" }));
    await userEvent.click(screen.getByRole("button", { name: "创建板子" }));

    expect(await screen.findByText("板子名称已存在")).toBeInTheDocument();
  });

  it("renders preset template buttons", () => {
    render(
      <BoardCreateModal isOpen={true} roles={mockRoles} onCreateComplete={vi.fn()} onClose={vi.fn()} />
    );

    expect(screen.getByText("6人新手局")).toBeInTheDocument();
    expect(screen.getByText("8人标准局")).toBeInTheDocument();
    expect(screen.getByText("9人进阶局")).toBeInTheDocument();
  });
});
