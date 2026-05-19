import { FormEvent, useState } from "react";

import type { AdminAgentDto, AdminPlayerDto } from "../types";

interface AdminPlayersPageProps {
  players: AdminPlayerDto[];
  agents?: AdminAgentDto[];
  onRefresh: () => void;
  onShowCreate: () => void;
  onCreateSubmit: (payload: { name: string; is_ai: boolean; agent_id?: string | null }) => Promise<void>;
  onToggleAi?: (player: AdminPlayerDto) => Promise<void>;
  onDelete?: (playerId: string) => Promise<void>;
}

interface PlayerFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (values: { name: string; is_ai: boolean; agent_id?: string | null }) => Promise<void>;
  agents: AdminAgentDto[];
}

export function PlayerFormModal({ isOpen, onClose, onSubmit, agents }: PlayerFormModalProps) {
  const [name, setName] = useState("");
  const [isAi, setIsAi] = useState(false);
  const [agentId, setAgentId] = useState<string>("");
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) { setMessage("请先填写玩家名称"); return; }
    setSubmitting(true); setMessage(null);
    try {
      await onSubmit({ name: name.trim(), is_ai: isAi, agent_id: isAi && agentId ? agentId : null });
      setName(""); setIsAi(false); setAgentId("");
      onClose();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "新增玩家失败");
    } finally { setSubmitting(false); }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal-title">创建玩家</h3>
        <form className="admin-form" onSubmit={handleSubmit}>
          <div className="admin-form-row">
            <label htmlFor="player-name">玩家名称</label>
            <input id="player-name" aria-label="玩家名称" value={name} onChange={(e) => setName(e.target.value)} placeholder="输入名称" />
          </div>
          <div className="admin-form-row">
            <label>
              <input type="checkbox" checked={isAi} onChange={(e) => setIsAi(e.target.checked)} />
              {" "}AI 玩家
            </label>
          </div>
          {isAi && agents.length > 0 ? (
            <div className="admin-form-row">
              <label htmlFor="player-agent">关联 AI 人设</label>
              <select id="player-agent" value={agentId} onChange={(e) => setAgentId(e.target.value)}>
                <option value="">不指定</option>
                {agents.map((a) => (
                  <option key={a.agent_id} value={a.agent_id}>{a.name}</option>
                ))}
              </select>
            </div>
          ) : null}
          <div className="admin-form-actions">
            <button className="primary-action" type="submit" disabled={submitting}>{submitting ? "保存中..." : "确认"}</button>
            <button className="ghost-action" type="button" onClick={onClose}>取消</button>
          </div>
          {message ? <p className="admin-form-message" role="alert">{message}</p> : null}
        </form>
      </div>
    </div>
  );
}

export function AdminPlayersPage({ players, agents = [], onRefresh, onShowCreate, onCreateSubmit, onToggleAi, onDelete }: AdminPlayersPageProps) {
  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="scene-kicker">PLAYERS</p>
          <h2>玩家管理</h2>
        </div>
        <div className="admin-actions">
          <button className="primary-action" type="button" onClick={onShowCreate}>
            + 新建玩家
          </button>
          <button className="ghost-action" type="button" onClick={onRefresh}>
            刷新
          </button>
        </div>
      </header>
      {players.length === 0 ? (
        <div className="admin-empty-state">
          <p>暂无玩家</p>
          <button className="primary-action" type="button" onClick={onShowCreate}>创建第一个玩家</button>
        </div>
      ) : (
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
                <td>{agents.find((a) => a.agent_id === player.agent_id)?.name ?? player.agent_id ?? "-"}</td>
                <td>
                  <span className="admin-row-actions">
                    <button className="ghost-action compact" type="button" onClick={() => void onToggleAi?.(player)}>
                      {player.is_ai ? "设为真人" : "设为 AI"}
                    </button>
                    <button className="danger-action compact" type="button" onClick={() => {
                      if (window.confirm(`确定删除玩家「${player.name}」？`)) void onDelete?.(player.player_id);
                    }}>删除</button>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
