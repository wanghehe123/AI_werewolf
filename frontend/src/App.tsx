import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes, useParams } from "react-router-dom";

import { createGame, fetchAgents, fetchBoards, fetchGame, submitGameAction } from "./api";
import { GameTable } from "./GameTable";
import { LobbyPage } from "./LobbyPage";
import type { AgentProfile, BoardConfig, GameStateDto, SubmitActionInput } from "./types";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LobbyRoute />} />
        <Route path="/games/:gameId" element={<GameRoute />} />
      </Routes>
    </BrowserRouter>
  );
}

function LobbyRoute() {
  const [boards, setBoards] = useState<BoardConfig[]>([]);
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchBoards(), fetchAgents()])
      .then(([boardData, agentData]) => {
        setBoards(boardData);
        setAgents(agentData);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "加载大厅失败"));
  }, []);

  if (error) {
    return <StatusScreen title="大厅加载失败" detail={error} />;
  }
  if (boards.length === 0 || agents.length === 0) {
    return <StatusScreen title="正在整理牌桌" detail="正在读取后端板子和 AI 玩家。" />;
  }
  return <LobbyPage boards={boards} agents={agents} createGame={createGame} />;
}

function GameRoute() {
  const { gameId } = useParams();
  const [game, setGame] = useState<GameStateDto | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!gameId) {
      return;
    }
    fetchGame(gameId)
      .then(setGame)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "加载游戏失败"));
  }, [gameId]);

  async function handleAction(action: SubmitActionInput) {
    if (!gameId) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      setGame(await submitGameAction(gameId, action));
    } catch (err) {
      setError(err instanceof Error ? err.message : "行动失败");
    } finally {
      setPending(false);
    }
  }

  if (error) {
    return <StatusScreen title="游戏暂时卡住了" detail={error} />;
  }
  if (!game) {
    return <StatusScreen title="正在进入房间" detail="正在恢复当前游戏状态。" />;
  }
  return <GameTable game={game} onSubmitAction={handleAction} pending={pending} />;
}

function StatusScreen({ title, detail }: { title: string; detail: string }) {
  return (
    <main className="status-screen">
      <p className="scene-kicker">AI WEREWOLF</p>
      <h1>{title}</h1>
      <p>{detail}</p>
    </main>
  );
}
