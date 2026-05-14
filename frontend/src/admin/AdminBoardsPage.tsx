import { FormEvent, useState } from "react";

import type { AdminBoardDto } from "../types";

interface AdminBoardsPageProps {
  boards: AdminBoardDto[];
  onRefresh: () => void;
  onCreate?: (payload: Omit<AdminBoardDto, "board_id" | "roles" | "created_at">) => Promise<void>;
}

export function AdminBoardsPage({ boards, onRefresh, onCreate }: AdminBoardsPageProps) {
  const [name, setName] = useState("");
  const [players, setPlayers] = useState(6);

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
            </tr>
          ))}
        </tbody>
      </table>
      {boards.length === 0 ? <p className="admin-empty">暂无板子</p> : null}
    </section>
  );
}
