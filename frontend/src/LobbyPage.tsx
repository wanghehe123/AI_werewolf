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
  const roleOptions = selectedBoard?.roles ?? [];
  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>(() => agents.slice(0, requiredAgents).map((agent) => agent.agent_id));
  const [humanPlayerName, setHumanPlayerName] = useState("");
  const [humanRoleKey, setHumanRoleKey] = useState("random");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canStart = Boolean(selectedBoard) && humanPlayerName.trim().length > 0 && selectedAgentIds.length === requiredAgents && !pending;

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
        human_player_id: humanPlayerIdFromName(humanPlayerName),
        human_player_name: humanPlayerName.trim(),
        human_role_key: humanRoleKey,
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
    <main className="flex flex-col items-center gap-8 max-w-[1180px] mx-auto px-4 py-8">
      <section className="min-h-[28vh] grid content-end text-center py-[38px]">
        <p className="text-[0.78rem] tracking-[0.12em] uppercase text-[var(--color-gold)] font-extrabold mb-2">AI WEREWOLF</p>
        <h1 className="text-[clamp(2rem,5vw,4.5rem)] leading-none">今晚，一个人开一桌狼人杀</h1>
        <p className="max-w-[680px] text-[var(--color-text-dim)] text-[1.05rem]">选择后台配置好的板子和 AI 玩家，进入第一版 MVP 对局闭环。</p>
      </section>

      <section className="grid grid-cols-[1fr_1.25fr_0.85fr] gap-[18px] w-full max-md:grid-cols-1">
        <div className="p-[18px] rounded-lg border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]">
          <div className="mb-3.5 text-[#f0d9ab] font-extrabold">选择板子</div>
          <div className="flex flex-col gap-2.5">
            {boards.map((board) => (
              <button
                className={`grid gap-1.5 p-[15px] rounded-lg border cursor-pointer transition-all w-full text-left border-white/[0.09] bg-white/[0.045] text-[var(--color-text)] ${board.board_id === selectedBoard?.board_id ? "!border-[var(--color-gold)] opacity-80 bg-[rgba(148,44,32,0.24)]" : ""}`}
                key={board.board_id}
                onClick={() => {
                  setBoardId(board.board_id);
                  setSelectedAgentIds(agents.slice(0, Math.max(board.player_count - 1, 0)).map((agent) => agent.agent_id));
                  setHumanRoleKey("random");
                }}
              >
                <strong>{board.name}</strong>
                <span className="text-[#b9aa92]">{board.player_count} 人局 · {board.sheriff_enabled ? "有警长" : "无警长"}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="p-[18px] rounded-lg border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]">
          <label className="mb-3.5 text-[#f0d9ab] font-extrabold block" htmlFor="human-player-name">玩家名称</label>
          <input
            id="human-player-name"
            aria-label="玩家名称"
            className="w-full min-h-[42px] border border-white/[0.14] rounded-lg px-3 bg-white/[0.06] text-[var(--color-text)]"
            value={humanPlayerName}
            onChange={(event) => setHumanPlayerName(event.target.value)}
            placeholder="输入你在本局里的名字"
            maxLength={18}
          />
          <p className="text-[#b9aa92] mt-2 mb-5">AI 会用这个名字称呼你，避免把真人玩家识别成 human。</p>
          <label className="mb-3.5 text-[#f0d9ab] font-extrabold block" htmlFor="human-role-select">选择你的职业</label>
          <p className="text-[#b9aa92]">默认随机；选择具体职业可方便测试夜晚技能和发言视角。</p>
          <select
            id="human-role-select"
            className="w-full min-h-[42px] border border-white/[0.14] rounded-lg px-3 bg-white/[0.06] text-[var(--color-text)]"
            aria-label="选择你的职业"
            value={humanRoleKey}
            onChange={(event) => setHumanRoleKey(event.target.value)}
          >
            <option value="random">随机身份</option>
            {roleOptions.map((role) => (
              <option key={role.role_key} value={role.role_key}>
                {roleLabel(role.role_key)} x{role.count}
              </option>
            ))}
          </select>
        </div>

        <div className="p-[18px] rounded-lg border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]">
          <div className="mb-3.5 text-[#f0d9ab] font-extrabold">选择 AI 玩家</div>
          <p className="text-[#b9aa92]">需要选择 {requiredAgents} 位 AI 玩家</p>
          <div className="flex flex-col gap-2.5 max-h-[300px] overflow-y-auto">
            {agents.map((agent) => (
              <label
                className={`grid grid-cols-[auto_42px_1fr] items-center gap-2.5 p-[11px] rounded-lg border cursor-pointer transition-all w-full border-white/[0.09] bg-white/[0.045] text-[var(--color-text)] ${selectedAgentIds.includes(agent.agent_id) ? "!border-[var(--color-gold)] opacity-80 bg-[rgba(148,44,32,0.24)]" : ""}`}
                key={agent.agent_id}
              >
                <input type="checkbox" checked={selectedAgentIds.includes(agent.agent_id)} onChange={() => toggleAgent(agent.agent_id)} className="accent-[var(--color-gold)]" />
                <span className="grid place-items-center w-[42px] h-[42px] rounded-full bg-linear-to-br from-[#31201a] to-[#a53829] text-[#ffe1a8] font-black">{agent.name.slice(0, 1)}</span>
                <span className="grid gap-[3px]">
                  <strong>{agent.name}</strong>
                  <em className="text-[#b9aa92] not-italic">{agent.persona}</em>
                </span>
              </label>
            ))}
          </div>
        </div>

        <aside className="grid content-start gap-3.5 p-[18px] rounded-lg border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]">
          <div className="mb-3.5 text-[#f0d9ab] font-extrabold">开局确认</div>
          <p>{selectedBoard?.name ?? "暂无板子"}</p>
          <strong>{selectedAgentIds.length}/{requiredAgents} AI 已选择</strong>
          {error && <p className="text-[#ff9b8e]">{error}</p>}
          <button className="px-6 py-3 rounded-lg bg-linear-to-br from-[#e0b866] to-[var(--color-red-werewolf)] text-[var(--color-warm-bg)] font-extrabold disabled:opacity-50" disabled={!canStart} onClick={handleCreateGame}>
            开局
          </button>
        </aside>
      </section>
    </main>
  );
}

function roleLabel(roleKey: string): string {
  const labels: Record<string, string> = {
    werewolf: "狼人",
    seer: "预言家",
    witch: "女巫",
    hunter: "猎人",
    villager: "村民",
    guard: "守卫",
    guardian: "守卫"
  };
  return labels[roleKey] ?? roleKey;
}

function humanPlayerIdFromName(name: string): string {
  const encoded = Array.from(name.trim())
    .map((char) => char.codePointAt(0)?.toString(36) ?? "")
    .filter(Boolean)
    .join("_");
  return `player_${encoded || "guest"}`.slice(0, 64);
}
