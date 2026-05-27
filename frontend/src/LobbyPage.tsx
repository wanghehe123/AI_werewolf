import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { avatarFor } from "./game-ui/defaultAvatars";
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
    <main className="wolf-page">
      <section className="wolf-content mx-auto grid min-h-screen w-full max-w-[1480px] grid-rows-[auto_1fr] gap-6 px-8 py-8">
        <header className="grid grid-cols-[280px_1fr_280px] items-start gap-6">
          <div>
            <div className="flex items-end gap-3">
              <h2 className="text-[2.8rem] font-black leading-none tracking-[0.02em] text-[#24304f]">狼人杀</h2>
              <span className="pb-1 text-sm font-bold uppercase tracking-[0.15em] text-[#9aa8db]">Werewolf</span>
            </div>
            <p className="mt-3 text-[var(--color-wolf-muted)]">和 AI 玩家推理对局</p>
          </div>

          <div className="text-center">
            <h1 className="text-[3rem] font-black leading-tight tracking-[0.04em] text-[#17213d]">今晚，找一桌狼人杀</h1>
            <p className="mt-3 text-base text-[var(--color-wolf-muted)]">选择板子、配置身份，和 AI 玩家一起开始推理。</p>
            <div className="wolf-glass mx-auto mt-6 inline-flex items-center gap-6 rounded-full px-8 py-3 text-sm font-semibold text-[#526188]">
              <span>在线 AI <strong className="ml-2 text-[#17213d]">{agents.length}</strong></span>
              <span className="h-4 w-px bg-[var(--color-wolf-line)]" />
              <span>可用板子 <strong className="ml-2 text-[#17213d]">{boards.length}</strong></span>
              <span className="h-4 w-px bg-[var(--color-wolf-line)]" />
              <span>快速配置 AI 对局</span>
            </div>
          </div>

          <div className="flex justify-end">
            <div className="wolf-glass flex items-center gap-3 rounded-[22px] px-4 py-3">
              <img className="h-12 w-12 rounded-full shadow-lg" src={avatarFor(null, humanPlayerName || "guest")} alt="" />
              <div className="min-w-0">
                <p className="text-sm font-bold text-[#263251]">{humanPlayerName.trim() || "未命名玩家"}</p>
                <p className="text-xs text-[var(--color-wolf-muted)]">Lv.12</p>
              </div>
            </div>
          </div>
        </header>

        <section className="grid grid-cols-[280px_minmax(0,1fr)_340px] gap-5">
          <aside className="grid content-start gap-4">
            <div className="wolf-glass rounded-[24px] p-5">
              <p className="mb-4 text-base font-black text-[#1e2948]">快速开始</p>
              <button
                className="grid w-full grid-cols-[52px_1fr_auto] items-center gap-4 rounded-[18px] border border-[#dbe5fb] bg-white/60 px-4 py-4 text-left transition hover:border-[#9eb2ff] hover:bg-white"
                type="button"
              >
                <span className="grid h-12 w-12 place-items-center rounded-full bg-white text-2xl shadow-md">⚡</span>
                <span>
                  <strong className="block text-[#1e2948]">快速匹配</strong>
                  <span className="text-sm text-[var(--color-wolf-muted)]">自动选择推荐配置</span>
                </span>
                <span className="text-xl text-[#6c7bb4]">›</span>
              </button>
            </div>

            <div className="wolf-glass rounded-[24px] p-5">
              <p className="mb-4 text-base font-black text-[#1e2948]">选择板子</p>
              <div className="grid gap-3">
                {boards.map((board) => (
                  <button
                    className={`grid w-full grid-cols-[46px_1fr] items-center gap-3 rounded-[18px] border px-4 py-3 text-left transition ${
                      board.board_id === selectedBoard?.board_id
                        ? "border-[#8ba1ff] bg-[#eef3ff] shadow-[0_12px_28px_rgba(93,119,255,0.14)]"
                        : "border-[#dfe7f8] bg-white/55 hover:border-[#b4c3ff]"
                    }`}
                    key={board.board_id}
                    onClick={() => {
                      setBoardId(board.board_id);
                      setSelectedAgentIds(agents.slice(0, Math.max(board.player_count - 1, 0)).map((agent) => agent.agent_id));
                      setHumanRoleKey("random");
                    }}
                  >
                    <span className="grid h-11 w-11 place-items-center rounded-full bg-white text-xl shadow-sm">{board.sheriff_enabled ? "♛" : "☀"}</span>
                    <span>
                      <strong className="block text-[#1e2948]">{board.name}</strong>
                      <span className="text-sm text-[var(--color-wolf-muted)]">{board.player_count} 人局 · {board.sheriff_enabled ? "有警长" : "无警长"}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </aside>

          <section className="wolf-glass rounded-[28px] p-6">
            <div className="mb-5 flex items-end justify-between border-b border-[var(--color-wolf-line)] pb-4">
              <div>
                <p className="text-sm font-bold text-[var(--color-wolf-blue)]">房间配置</p>
                <h2 className="mt-1 text-2xl font-black text-[#17213d]">配置你的房间</h2>
              </div>
              <span className="rounded-full bg-[#eef3ff] px-4 py-2 text-sm font-bold text-[#526188]">
                {selectedAgentIds.length}/{requiredAgents} AI
              </span>
            </div>

            <div className="grid grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] gap-5">
              <div className="grid content-start gap-5">
                <label className="grid gap-2 text-sm font-bold text-[#33415f]" htmlFor="human-player-name">
                  玩家名称
                  <input
                    id="human-player-name"
                    aria-label="玩家名称"
                    className="min-h-[48px] rounded-[18px] border border-[#dce5f8] bg-white/70 px-4 text-[#17213d] outline-none transition placeholder:text-[#a5b2cf] focus:border-[#8198ff] focus:bg-white"
                    value={humanPlayerName}
                    onChange={(event) => setHumanPlayerName(event.target.value)}
                    placeholder="输入你在本局里的名字"
                    maxLength={18}
                  />
                </label>

                <label className="grid gap-2 text-sm font-bold text-[#33415f]" htmlFor="human-role-select">
                  选择你的职业
                  <select
                    id="human-role-select"
                    className="min-h-[48px] rounded-[18px] border border-[#dce5f8] bg-white/70 px-4 text-[#17213d] outline-none transition focus:border-[#8198ff] focus:bg-white"
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
                </label>

                <div className="rounded-[22px] border border-[#dce5f8] bg-white/50 p-4">
                  <p className="text-sm font-black text-[#263251]">身份构成</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {roleOptions.map((role) => (
                      <span className={`wolf-role-badge role-${role.role_key}`} key={role.role_key}>{roleLabel(role.role_key)} x{role.count}</span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid content-start gap-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-black text-[#263251]">选择 AI 玩家</p>
                  <span className="text-sm text-[var(--color-wolf-muted)]">需要选择 {requiredAgents} 位 AI 玩家</span>
                </div>
                <div className="grid max-h-[460px] gap-3 overflow-y-auto pr-1">
                  {agents.map((agent, index) => (
                    <label
                      className={`grid cursor-pointer grid-cols-[auto_52px_1fr] items-center gap-3 rounded-[18px] border px-3 py-3 transition ${
                        selectedAgentIds.includes(agent.agent_id)
                          ? "border-[#8ba1ff] bg-[#eef3ff]"
                          : "border-[#dfe7f8] bg-white/55 hover:border-[#b4c3ff]"
                      }`}
                      key={agent.agent_id}
                    >
                      <input type="checkbox" checked={selectedAgentIds.includes(agent.agent_id)} onChange={() => toggleAgent(agent.agent_id)} className="accent-[var(--color-wolf-blue)]" />
                      <img className="h-12 w-12 rounded-full shadow-md" src={avatarFor(agent.avatar_url, agent.agent_id || index)} alt="" />
                      <span className="min-w-0">
                        <strong className="block text-[#1e2948]">{agent.name}</strong>
                        <em className="block truncate text-sm not-italic text-[var(--color-wolf-muted)]">{agent.persona}</em>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </section>

          <aside className="grid content-start gap-5">
            <section className="wolf-glass rounded-[24px] p-5">
              <p className="mb-4 text-base font-black text-[#1e2948]">开局确认</p>
              <div className="grid gap-3 rounded-[20px] bg-white/55 p-4">
                <p className="font-black text-[#17213d]">{selectedBoard?.name ?? "暂无板子"}</p>
                <p className="text-sm text-[var(--color-wolf-muted)]">{selectedBoard?.player_count ?? 0} 人局 · {selectedBoard?.sheriff_enabled ? "有警长" : "无警长"}</p>
                <strong className="text-[#526188]">{selectedAgentIds.length}/{requiredAgents} AI 已选择</strong>
              </div>
              {error && <p className="mt-3 text-sm font-bold text-[var(--color-wolf-red)]">{error}</p>}
              <button className="wolf-primary mt-5 min-h-[56px] w-full rounded-[20px] px-6 py-3 text-base font-black disabled:cursor-not-allowed disabled:opacity-50" disabled={!canStart} onClick={handleCreateGame}>
                开局
              </button>
            </section>

            <section className="wolf-glass rounded-[24px] p-5">
              <p className="text-base font-black text-[#1e2948]">对局提示</p>
              <p className="mt-3 text-sm leading-6 text-[var(--color-wolf-muted)]">这是一个极简 AI 对局大厅。创建后会进入你的专属房间，房间令牌会自动保存到当前浏览器会话。</p>
            </section>
          </aside>
        </section>
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
