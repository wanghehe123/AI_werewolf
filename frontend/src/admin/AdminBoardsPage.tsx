import { FormEvent, useState } from "react";

import type { AdminBoardDto } from "../types";

interface AdminBoardsPageProps {
  boards: AdminBoardDto[];
  onRefresh: () => void;
  onCreate?: (payload: Omit<AdminBoardDto, "board_id" | "roles" | "created_at">) => Promise<void>;
  onToggleEnabled?: (board: AdminBoardDto) => Promise<void>;
  onReplaceRoles?: (boardId: string, roles: Array<{ role_key: string; count: number }>) => Promise<void>;
  onDelete?: (boardId: string) => Promise<void>;
}

export function AdminBoardsPage({ boards, onRefresh, onCreate, onToggleEnabled, onReplaceRoles, onDelete }: AdminBoardsPageProps) {
  const [name, setName] = useState("");
  const [players, setPlayers] = useState(6);
  const [roleSpecs, setRoleSpecs] = useState<Record<string, string>>({});

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!onCreate || !name) {
      return;
    }
    await onCreate({
      name,
      description: null,
      min_players: players,
      max_players: players,
      sheriff_enabled: false,
      enabled: true
    });
    setName("");
    setPlayers(6);
    onRefresh();
  }

  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="scene-kicker">BOARDS</p>
          <h2>板子管理</h2>
        </div>
        <button className="ghost-action" type="button" onClick={onRefresh}>
          刷新
        </button>
      </header>
      <form className="admin-inline-form" onSubmit={handleSubmit}>
        <input aria-label="板子名称" placeholder="板子名称" value={name} onChange={(event) => setName(event.target.value)} />
        <input
          aria-label="人数"
          type="number"
          min={1}
          value={players}
          onChange={(event) => setPlayers(Number(event.target.value))}
        />
        <button className="primary-action" type="submit" disabled={!onCreate}>
          新增板子
        </button>
      </form>
      <table className="admin-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>人数</th>
            <th>角色</th>
            <th>警长</th>
            <th>状态</th>
            <th>角色配置</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {boards.map((board) => (
            <tr key={board.board_id}>
              <td>{board.name}</td>
              <td>
                {board.min_players}-{board.max_players}
              </td>
              <td>{board.roles.length > 0 ? board.roles.map((role) => `${role.role_key} x${role.count}`).join(" / ") : "未配置"}</td>
              <td>{board.sheriff_enabled ? "开启" : "关闭"}</td>
              <td>{board.enabled ? "启用" : "停用"}</td>
              <td>
                <form
                  className="admin-role-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const roles = parseRoleSpec(roleSpecs[board.board_id] ?? "");
                    if (roles.length > 0) {
                      void onReplaceRoles?.(board.board_id, roles);
                    }
                  }}
                >
                  <input
                    aria-label={`${board.name} 角色配置`}
                    placeholder="werewolf:2,seer:1,villager:3"
                    value={roleSpecs[board.board_id] ?? ""}
                    onChange={(event) => setRoleSpecs({ ...roleSpecs, [board.board_id]: event.target.value })}
                  />
                  <button className="ghost-action compact" type="submit">
                    保存
                  </button>
                </form>
              </td>
              <td>
                <span className="admin-row-actions">
                  <button className="ghost-action compact" type="button" onClick={() => void onToggleEnabled?.(board)}>
                    {board.enabled ? "停用" : "启用"}
                  </button>
                  <button className="danger-action compact" type="button" onClick={() => void onDelete?.(board.board_id)}>
                    删除
                  </button>
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {boards.length === 0 ? <p className="admin-empty">暂无板子</p> : null}
    </section>
  );
}

function parseRoleSpec(value: string): Array<{ role_key: string; count: number }> {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const [roleKey, count] = part.split(":");
      return { role_key: roleKey.trim(), count: Number(count) };
    })
    .filter((role) => role.role_key && Number.isInteger(role.count) && role.count > 0);
}
