import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes, useNavigate, useParams } from "react-router-dom";

import {
  adminLogin,
  adminLogout,
  createAdminAgent,
  createAdminBoard,
  createAdminLlmProvider,
  createAdminPlayer,
  createAdminRoleModelBinding,
  deleteAdminAgent,
  deleteAdminBoard,
  deleteAdminPlayer,
  fetchAdminAgents,
  fetchAdminBoards,
  fetchAdminGames,
  fetchAdminLlmProviders,
  fetchAdminPlayers,
  fetchAdminRoleModelBindings,
  fetchAdminRoles,
  fetchAgents,
  fetchBoards,
  fetchGame,
  seedAdminRoles,
  updateAdminAgent,
  updateAdminBoard,
  updateAdminPlayer,
  replaceAdminBoardRoles,
  createGame,
  submitGameAction
} from "./api";
import { AdminAgentsPage } from "./admin/AdminAgentsPage";
import { AdminBoardsPage } from "./admin/AdminBoardsPage";
import { AdminDashboardPage } from "./admin/AdminDashboardPage";
import { AdminGamesPage } from "./admin/AdminGamesPage";
import { AdminLayout } from "./admin/AdminLayout";
import { AdminLoginPage } from "./admin/AdminLoginPage";
import { AdminLlmPage } from "./admin/AdminLlmPage";
import { AdminPlayersPage } from "./admin/AdminPlayersPage";
import { AdminRolesPage } from "./admin/AdminRolesPage";
import { GameTable } from "./GameTable";
import { LobbyPage } from "./LobbyPage";
import type { AdminAgentDto, AdminBoardDto, AdminGameDto, AdminLlmProviderDto, AdminPlayerDto, AdminRoleModelBindingDto, AdminRoleDto, AgentProfile, BoardConfig, GameStateDto, SubmitActionInput } from "./types";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LobbyRoute />} />
        <Route path="/games/:gameId" element={<GameRoute />} />
        <Route path="/admin/login" element={<AdminLoginRoute />} />
        <Route path="/admin" element={<AdminShellRoute />}>
          <Route index element={<AdminDashboardPage />} />
          <Route path="players" element={<AdminPlayersRoute />} />
          <Route path="agents" element={<AdminAgentsRoute />} />
          <Route path="boards" element={<AdminBoardsRoute />} />
          <Route path="roles" element={<AdminRolesRoute />} />
          <Route path="llm" element={<AdminLlmRoute />} />
          <Route path="games" element={<AdminGamesRoute />} />
        </Route>
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

function AdminLoginRoute() {
  const navigate = useNavigate();
  return (
    <AdminLoginPage
      login={async (username, password) => {
        await adminLogin(username, password);
        navigate("/admin");
      }}
    />
  );
}

function AdminShellRoute() {
  const navigate = useNavigate();
  return (
    <AdminLayout
      logout={async () => {
        await adminLogout();
        navigate("/admin/login");
      }}
    />
  );
}

function useAdminData<T>(load: () => Promise<T[]>) {
  const [items, setItems] = useState<T[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setError(null);
      setItems(await load());
    } catch (err) {
      setError(err instanceof Error ? err.message : "后台数据加载失败");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return { items, error, refresh };
}

function AdminPlayersRoute() {
  const { items, error, refresh } = useAdminData<AdminPlayerDto>(fetchAdminPlayers);
  if (error) {
    return <AdminStatus title="玩家加载失败" detail={error} />;
  }
  return (
    <AdminPlayersPage
      players={items}
      onRefresh={refresh}
      onCreate={async (payload) => void (await createAdminPlayer(payload))}
      onToggleAi={async (player) => {
        await updateAdminPlayer(player.player_id, { is_ai: !player.is_ai });
        await refresh();
      }}
      onDelete={async (playerId) => {
        await deleteAdminPlayer(playerId);
        await refresh();
      }}
    />
  );
}

function AdminAgentsRoute() {
  const { items, error, refresh } = useAdminData<AdminAgentDto>(fetchAdminAgents);
  if (error) {
    return <AdminStatus title="AI 加载失败" detail={error} />;
  }
  return (
    <AdminAgentsPage
      agents={items}
      onRefresh={refresh}
      onCreate={async (payload) => void (await createAdminAgent(payload))}
      onToggleEnabled={async (agent) => {
        await updateAdminAgent(agent.agent_id, { enabled: !agent.enabled });
        await refresh();
      }}
      onDelete={async (agentId) => {
        await deleteAdminAgent(agentId);
        await refresh();
      }}
    />
  );
}

function AdminBoardsRoute() {
  const { items, error, refresh } = useAdminData<AdminBoardDto>(fetchAdminBoards);
  if (error) {
    return <AdminStatus title="板子加载失败" detail={error} />;
  }
  return (
    <AdminBoardsPage
      boards={items}
      onRefresh={refresh}
      onCreate={async (payload) => void (await createAdminBoard(payload))}
      onToggleEnabled={async (board) => {
        await updateAdminBoard(board.board_id, { enabled: !board.enabled });
        await refresh();
      }}
      onReplaceRoles={async (boardId, roles) => {
        await replaceAdminBoardRoles(boardId, roles);
        await refresh();
      }}
      onDelete={async (boardId) => {
        await deleteAdminBoard(boardId);
        await refresh();
      }}
    />
  );
}

function AdminRolesRoute() {
  const { items, error, refresh } = useAdminData<AdminRoleDto>(fetchAdminRoles);
  if (error) {
    return <AdminStatus title="角色加载失败" detail={error} />;
  }
  return (
    <AdminRolesPage
      roles={items}
      onRefresh={refresh}
      onSeed={async () => {
        await seedAdminRoles();
        await refresh();
      }}
    />
  );
}

function AdminGamesRoute() {
  const { items, error, refresh } = useAdminData<AdminGameDto>(fetchAdminGames);
  if (error) {
    return <AdminStatus title="游戏记录加载失败" detail={error} />;
  }
  return <AdminGamesPage games={items} onRefresh={refresh} />;
}

function AdminLlmRoute() {
  const providersState = useAdminData<AdminLlmProviderDto>(fetchAdminLlmProviders);
  const bindingsState = useAdminData<AdminRoleModelBindingDto>(fetchAdminRoleModelBindings);
  const error = providersState.error ?? bindingsState.error;

  async function refresh() {
    await Promise.all([providersState.refresh(), bindingsState.refresh()]);
  }

  if (error) {
    return <AdminStatus title="模型配置加载失败" detail={error} />;
  }
  return (
    <AdminLlmPage
      providers={providersState.items}
      bindings={bindingsState.items}
      onRefresh={() => void refresh()}
      onCreateProvider={async (payload) => {
        await createAdminLlmProvider(payload);
        await refresh();
      }}
      onCreateBinding={async (payload) => {
        await createAdminRoleModelBinding(payload);
        await refresh();
      }}
    />
  );
}

function AdminStatus({ title, detail }: { title: string; detail: string }) {
  return (
    <section className="admin-page">
      <p className="scene-kicker">ADMIN</p>
      <h2>{title}</h2>
      <p className="error-text">{detail}</p>
    </section>
  );
}
