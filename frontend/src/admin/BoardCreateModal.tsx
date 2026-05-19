import { FormEvent, useState } from "react";

import { createAdminBoardComplete } from "../api";
import type { AdminBoardDto, AdminBoardRoleDto, AdminRoleDto } from "../types";
import { RolePicker } from "./RolePicker";

interface BoardCreateModalProps {
  isOpen: boolean;
  roles: AdminRoleDto[];
  onCreateComplete: (payload: Parameters<typeof createAdminBoardComplete>[0]) => Promise<AdminBoardDto>;
  onClose: () => void;
}

interface Preset {
  label: string;
  name: string;
  players: number;
  sheriff: boolean;
  roles: AdminBoardRoleDto[];
}

const PRESETS: Preset[] = [
  {
    label: "6人新手局",
    name: "6人新手局",
    players: 6,
    sheriff: false,
    roles: [
      { role_key: "werewolf", count: 2 },
      { role_key: "seer", count: 1 },
      { role_key: "villager", count: 3 },
    ],
  },
  {
    label: "8人标准局",
    name: "8人预女猎",
    players: 8,
    sheriff: true,
    roles: [
      { role_key: "werewolf", count: 2 },
      { role_key: "seer", count: 1 },
      { role_key: "witch", count: 1 },
      { role_key: "hunter", count: 1 },
      { role_key: "villager", count: 3 },
    ],
  },
  {
    label: "9人进阶局",
    name: "9人进阶局",
    players: 9,
    sheriff: true,
    roles: [
      { role_key: "werewolf", count: 3 },
      { role_key: "seer", count: 1 },
      { role_key: "witch", count: 1 },
      { role_key: "hunter", count: 1 },
      { role_key: "villager", count: 3 },
    ],
  },
];

export function BoardCreateModal({ isOpen, roles, onCreateComplete, onClose }: BoardCreateModalProps) {
  const [name, setName] = useState("");
  const [players, setPlayers] = useState(6);
  const [sheriff, setSheriff] = useState(true);
  const [selectedRoles, setSelectedRoles] = useState<AdminBoardRoleDto[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  function applyPreset(preset: Preset) {
    setName(preset.name);
    setPlayers(preset.players);
    setSheriff(preset.sheriff);
    setSelectedRoles(preset.roles);
    setMessage(null);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setMessage("请填写板子名称");
      return;
    }
    const total = selectedRoles.reduce((sum, r) => sum + r.count, 0);
    if (total < players) {
      setMessage(`角色总数(${total})小于玩家人数(${players})`);
      return;
    }
    if (total > players) {
      setMessage(`角色总数(${total})大于玩家人数(${players})`);
      return;
    }
    setSubmitting(true);
    setMessage(null);
    try {
      await onCreateComplete({
        name: trimmedName,
        description: null,
        min_players: players,
        max_players: players,
        sheriff_enabled: sheriff,
        enabled: true,
        roles: selectedRoles,
      });
      setName("");
      setPlayers(6);
      setSheriff(true);
      setSelectedRoles([]);
      onClose();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "创建板子失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal-title">创建板子</h3>

        <div className="admin-presets">
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              className="ghost-action compact"
              type="button"
              onClick={() => applyPreset(preset)}
            >
              {preset.label}
            </button>
          ))}
        </div>

        <form className="admin-form" onSubmit={handleSubmit}>
          <div className="admin-form-row">
            <label htmlFor="board-name">板子名称</label>
            <input
              id="board-name"
              aria-label="板子名称"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="如: 8人标准局"
            />
          </div>

          <div className="admin-form-row">
            <label htmlFor="board-players">人数</label>
            <input
              id="board-players"
              aria-label="人数"
              type="number"
              min={1}
              value={players}
              onChange={(e) => setPlayers(Number(e.target.value))}
            />
          </div>

          <div className="admin-form-row">
            <label>
              <input
                type="checkbox"
                checked={sheriff}
                onChange={(e) => setSheriff(e.target.checked)}
              />
              {" "}警长竞选
            </label>
          </div>

          <RolePicker
            roles={roles}
            value={selectedRoles}
            onChange={setSelectedRoles}
            minPlayers={players}
            maxPlayers={players}
          />

          <div className="admin-form-actions">
            <button className="primary-action" type="submit" disabled={submitting}>
              {submitting ? "创建中..." : "创建板子"}
            </button>
            <button className="ghost-action" type="button" onClick={onClose}>
              取消
            </button>
          </div>
          {message ? <p className="admin-form-message" role="alert">{message}</p> : null}
        </form>
      </div>
    </div>
  );
}
