import { FormEvent, useState } from "react";

import type { AdminPlayerDto } from "../types";

interface AdminPlayersPageProps {
  players: AdminPlayerDto[];
  onRefresh: () => void;
  onCreate?: (payload: { name: string; is_ai: boolean }) => Promise<void>;
  onToggleAi?: (player: AdminPlayerDto) => Promise<void>;
  onDelete?: (playerId: string) => Promise<void>;
}

export function AdminPlayersPage({ players, onRefresh, onCreate, onToggleAi, onDelete }: AdminPlayersPageProps) {
  const [name, setName] = useState("");
  const [isAi, setIsAi] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!onCreate || !name) {
      return;
    }
    await onCreate({ name, is_ai: isAi });
    setName("");
    setIsAi(false);
    onRefresh();
  }

  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="scene-kicker">PLAYERS</p>
          <h2>玩家管理</h2>
        </div>
        <button className="ghost-action" type="button" onClick={onRefresh}>
          刷新
        </button>
      </header>
      <form className="admin-inline-form" onSubmit={handleSubmit}>
        <input aria-label="玩家名称" placeholder="玩家名称" value={name} onChange={(event) => setName(event.target.value)} />
        <label className="admin-check">
          <input type="checkbox" checked={isAi} onChange={(event) => setIsAi(event.target.checked)} />
          AI 玩家
        </label>
        <button className="primary-action" type="submit" disabled={!onCreate}>
          新增玩家
        </button>
      </form>
      <table className="admin-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>类型</th>
            <th>关联 AI</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {players.map((player) => (
            <tr key={player.player_id}>
              <td>{player.name}</td>
              <td>{player.is_ai ? "AI" : "真人"}</td>
              <td>{player.agent_id ?? "-"}</td>
              <td>
                <span className="admin-row-actions">
                  <button className="ghost-action compact" type="button" onClick={() => void onToggleAi?.(player)}>
                    {player.is_ai ? "设为真人" : "设为 AI"}
                  </button>
                  <button className="danger-action compact" type="button" onClick={() => void onDelete?.(player.player_id)}>
                    删除
                  </button>
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {players.length === 0 ? <p className="admin-empty">暂无玩家</p> : null}
    </section>
  );
}
