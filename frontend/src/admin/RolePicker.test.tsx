import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AdminBoardRoleDto, AdminRoleDto } from "../types";
import { RolePicker } from "./RolePicker";

const mockRoles: AdminRoleDto[] = [
  { role_key: "werewolf", name: "狼人", faction: "wolf", description: "夜晚可击杀一名玩家", night_action: true, enabled: true },
  { role_key: "seer", name: "预言家", faction: "good", description: "每晚查验一名玩家身份", night_action: true, enabled: true },
  { role_key: "witch", name: "女巫", faction: "good", description: "拥有一瓶解药和一瓶毒药", night_action: true, enabled: true },
  { role_key: "hunter", name: "猎人", faction: "good", description: "出局时可开枪带走一人", night_action: false, enabled: true },
  { role_key: "villager", name: "平民", faction: "good", description: "无特殊技能", night_action: false, enabled: true },
];

describe("RolePicker", () => {
  it("renders all available roles grouped by faction", () => {
    render(<RolePicker roles={mockRoles} value={[]} onChange={vi.fn()} />);

    expect(screen.getByText("狼人")).toBeInTheDocument();
    expect(screen.getByText("预言家")).toBeInTheDocument();
    expect(screen.getByText("女巫")).toBeInTheDocument();
    expect(screen.getByText("猎人")).toBeInTheDocument();
    expect(screen.getByText("平民")).toBeInTheDocument();
  });

  it("increments role count when clicking + button", async () => {
    const onChange = vi.fn();
    render(<RolePicker roles={mockRoles} value={[]} onChange={onChange} />);

    const werewolfRow = screen.getByText("狼人").closest(".role-picker-item")!;
    await userEvent.click(werewolfRow.querySelector('[aria-label="增加 狼人"]')!);

    expect(onChange).toHaveBeenCalledWith([{ role_key: "werewolf", count: 1 }]);
  });

  it("decrements role count when clicking - button", async () => {
    const onChange = vi.fn();
    const initial: AdminBoardRoleDto[] = [{ role_key: "werewolf", count: 2 }, { role_key: "villager", count: 1 }];
    render(<RolePicker roles={mockRoles} value={initial} onChange={onChange} />);

    const werewolfRow = screen.getByText("狼人").closest(".role-picker-item")!;
    await userEvent.click(werewolfRow.querySelector('[aria-label="减少 狼人"]')!);

    expect(onChange).toHaveBeenCalledWith(
      expect.arrayContaining([{ role_key: "werewolf", count: 1 }, { role_key: "villager", count: 1 }])
    );
  });

  it("shows current count for each role", () => {
    const initial: AdminBoardRoleDto[] = [{ role_key: "werewolf", count: 2 }, { role_key: "villager", count: 3 }];
    render(<RolePicker roles={mockRoles} value={initial} onChange={vi.fn()} />);

    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();

    const seerRow = screen.getByText("预言家").closest(".role-picker-item")!;
    expect(seerRow.textContent).toContain("0");
  });

  it("shows total player count", () => {
    const initial: AdminBoardRoleDto[] = [{ role_key: "werewolf", count: 2 }, { role_key: "villager", count: 1 }];
    render(<RolePicker roles={mockRoles} value={initial} onChange={vi.fn()} />);

    expect(screen.getByText(/共.*3.*人/)).toBeInTheDocument();
  });

  it("shows warning when total is below min players", () => {
    const initial: AdminBoardRoleDto[] = [{ role_key: "werewolf", count: 1 }];
    render(<RolePicker roles={mockRoles} value={initial} onChange={vi.fn()} minPlayers={6} maxPlayers={8} />);

    expect(screen.getByText(/至少.*6/)).toBeInTheDocument();
  });

  it("renders role descriptions", () => {
    render(<RolePicker roles={mockRoles} value={[]} onChange={vi.fn()} />);

    expect(screen.getByText("夜晚可击杀一名玩家")).toBeInTheDocument();
    expect(screen.getByText("无特殊技能")).toBeInTheDocument();
  });
});
