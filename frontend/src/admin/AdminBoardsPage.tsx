import { FormEvent, useState } from "react";

import type { AdminBoardDto } from "../types";

interface AdminBoardsPageProps {
  boards: AdminBoardDto[];
  onRefresh: () => void;
  onShowCreate: () => void;
  onToggleEnabled?: (board: AdminBoardDto) => Promise<void>;
  onReplaceRoles?: (boardId: string, roles: Array<{ role_key: string; count: number }>) => Promise<void>;
  onDelete?: (boardId: string) => Promise<void>;
}

export function AdminBoardsPage({ boards, onRefresh, onShowCreate, onToggleEnabled, onReplaceRoles, onDelete }: AdminBoardsPageProps) {
  const [roleSpecs, setRoleSpecs] = useState<Record<string, string>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggleExpand(boardId: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(boardId)) next.delete(boardId); else next.add(boardId);
      return next;
    });
  }

  async function handleSaveRoles(event: FormEvent, boardId: string) {
    event.preventDefault();
    const roles = parseRoleSpec(roleSpecs[boardId] ?? "");
    if (roles.length > 0 && onReplaceRoles) {
      await onReplaceRoles(boardId, roles);
      onRefresh();
    }
  }

  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="scene-kicker">BOARDS</p>
          <h2>板子管理</h2>
        </div>
        <div className="admin-actions">
          <button className="primary-action" type="button" onClick={onShowCreate}>
            + 新建板子
          </button>
          <button className="ghost-action" type="button" onClick={onRefresh}>
            刷新
          </button>
        </div>
      </header>

      {boards.length === 0 ? (
        <div className="admin-empty-state">
          <p>暂无板子</p>
          <button className="primary-action" type="button" onClick={onShowCreate}>
            创建第一个板子
          </button>
        </div>
      ) : (
        <div className="board-cards">
          {boards.map((board) => {
            const isExpanded = expanded.has(board.board_id);
            const roleText = board.roles.length > 0
              ? board.roles.map((role) => `${role.role_key} x${role.count}`).join(" / ")
              : "未配置";
            const totalRoles = board.roles.reduce((sum, r) => sum + r.count, 0);

            return (
              <div key={board.board_id} className={`board-card ${isExpanded ? "board-card-expanded" : ""}`}>
                <div className="board-card-header" onClick={() => toggleExpand(board.board_id)}>
                  <div className="board-card-title">
                    <span className="board-card-name">{board.name}</span>
                    <span className={`board-card-badge ${board.enabled ? "badge-on" : "badge-off"}`}>
                      {board.enabled ? "启用" : "停用"}
                    </span>
                  </div>
                  <span className="board-card-toggle">{isExpanded ? "▲" : "▼"}</span>
                </div>

                <div className="board-card-summary">
                  <span>
                    {board.min_players}-{board.max_players} 人 · {roleText} · 警长{board.sheriff_enabled ? "开启" : "关闭"}
                  </span>
                  {totalRoles > 0 ? <span className="board-card-total">角色 {totalRoles} 人</span> : null}
                </div>

                {isExpanded ? (
                  <div className="board-card-detail">
                    <form
                      className="admin-role-form"
                      onSubmit={(e) => handleSaveRoles(e, board.board_id)}
                    >
                      <input
                        aria-label={`${board.name} 角色配置`}
                        placeholder="werewolf:2,seer:1,villager:3"
                        value={roleSpecs[board.board_id] ?? ""}
                        onChange={(e) => setRoleSpecs({ ...roleSpecs, [board.board_id]: e.target.value })}
                      />
                      <button className="ghost-action compact" type="submit">保存角色</button>
                    </form>

                    <div className="board-card-actions">
                      <button
                        className="ghost-action compact"
                        type="button"
                        onClick={() => void onToggleEnabled?.(board)}
                      >
                        {board.enabled ? "停用" : "启用"}
                      </button>
                      <button
                        className="danger-action compact"
                        type="button"
                        onClick={() => {
                          if (window.confirm(`确定删除板子「${board.name}」？`)) {
                            void onDelete?.(board.board_id);
                          }
                        }}
                      >
                        删除
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
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
