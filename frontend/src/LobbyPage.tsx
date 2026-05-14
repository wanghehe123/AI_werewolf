import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { AgentProfile, BoardConfig, CreateGameRequest, GameStateDto } from "./types";

interface LobbyPageProps {
  boards: BoardConfig[];
  agents: AgentProfile[];
  createGame: (payload: CreateGameRequest) => Promise<Pick<GameStateDto, "game_id">>;
}

export function LobbyPage({ boards, agents, createGame }: LobbyPageProps) {
  const navigate = useNavigate();
  const [boardId, setBoardId] = useState(boards[0]?.board_id ?? "");
  const selectedBoard = useMemo(() => boards.find((board) => board.board_id === boardId) ?? boards[0], [boardId, boards]);
  const requiredAgents = Math.max((selectedBoard?.player_count ?? 1) - 1, 0);
  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>(() => agents.slice(0, requiredAgents).map((agent) => agent.agent_id));
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canStart = Boolean(selectedBoard) && selectedAgentIds.length === requiredAgents && !pending;

  function toggleAgent(agentId: string) {
    setSelectedAgentIds((current) => {
      if (current.includes(agentId)) {
        return current.filter((id) => id !== agentId);
      }
      if (current.length >= requiredAgents) {
        return current;
      }
      return [...current, agentId];
    });
  }

  async function handleCreateGame() {
    if (!selectedBoard) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      const game = await createGame({
        board_id: selectedBoard.board_id,
        human_player_id: "human",
        agent_ids: selectedAgentIds
      });
      navigate(`/games/${game.game_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "开局失败");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="lobby-shell">
      <section className="lobby-hero">
        <p className="scene-kicker">AI WEREWOLF</p>
        <h1>今晚，一个人开一桌狼人杀</h1>
        <p>选择后台配置好的板子和 AI 玩家，进入第一版 MVP 对局闭环。</p>
      </section>

      <section className="lobby-grid">
        <div className="config-panel">
          <div className="panel-title">选择板子</div>
          <div className="board-list">
            {boards.map((board) => (
              <button
                className={`board-card ${board.board_id === selectedBoard?.board_id ? "is-selected" : ""}`}
                key={board.board_id}
                onClick={() => {
                  setBoardId(board.board_id);
                  setSelectedAgentIds(agents.slice(0, Math.max(board.player_count - 1, 0)).map((agent) => agent.agent_id));
                }}
              >
                <strong>{board.name}</strong>
                <span>{board.player_count} 人局 · {board.sheriff_enabled ? "有警长" : "无警长"}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="config-panel">
          <div className="panel-title">选择 AI 玩家</div>
          <p className="helper-text">需要选择 {requiredAgents} 位 AI 玩家</p>
          <div className="agent-list">
            {agents.map((agent) => (
              <label className={`agent-card ${selectedAgentIds.includes(agent.agent_id) ? "is-selected" : ""}`} key={agent.agent_id}>
                <input type="checkbox" checked={selectedAgentIds.includes(agent.agent_id)} onChange={() => toggleAgent(agent.agent_id)} />
                <span className="avatar small">{agent.name.slice(0, 1)}</span>
                <span>
                  <strong>{agent.name}</strong>
                  <em>{agent.persona}</em>
                </span>
              </label>
            ))}
          </div>
        </div>

        <aside className="start-panel">
          <div className="panel-title">开局确认</div>
          <p>{selectedBoard?.name ?? "暂无板子"}</p>
          <strong>{selectedAgentIds.length}/{requiredAgents} AI 已选择</strong>
          {error && <p className="error-text">{error}</p>}
          <button className="primary-action" disabled={!canStart} onClick={handleCreateGame}>
            开局
          </button>
        </aside>
      </section>
    </main>
  );
}
