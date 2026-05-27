import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes, useNavigate, useParams } from "react-router-dom";

import {
  adminLogin,
  adminLogout,
  createAdminAgent,
  createAdminBoard,
  createAdminBoardComplete,
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
  seedAdminRoles,
  updateAdminAgent,
  updateAdminBoard,
  updateAdminPlayer,
  replaceAdminBoardRoles,
  createGame,
  submitGameAction,
  subscribeGameStream
} from "./api";
import { AdminAgentsPage } from "./admin/AdminAgentsPage";
import { AdminBoardsPage } from "./admin/AdminBoardsPage";
import { AdminDashboardPage } from "./admin/AdminDashboardPage";
import { AdminGamesPage } from "./admin/AdminGamesPage";
import { AdminLayout } from "./admin/AdminLayout";
import { AdminLoginPage } from "./admin/AdminLoginPage";
import { AdminLlmPage } from "./admin/AdminLlmPage";
import { AgentFormModal } from "./admin/AgentFormModal";
import { BoardCreateModal } from "./admin/BoardCreateModal";
import { AdminPlayersPage, PlayerFormModal } from "./admin/AdminPlayersPage";
import { AdminRolesPage } from "./admin/AdminRolesPage";
import { GameTable } from "./GameTable";
import { LobbyPage } from "./LobbyPage";
import type {
  AdminAgentDto,
  AdminBoardDto,
  AdminGameDto,
  AdminLlmProviderDto,
  AdminPlayerDto,
  AdminRoleModelBindingDto,
  AdminRoleDto,
  AgentProfile,
  BoardConfig,
  CreateGameRequest,
  GameStateDto,
  SubmitActionInput
} from "./types";
import { useGameStore } from "./stores/gameStore";
import { useTtsPlayback } from "./hooks/useTtsPlayback";
import { usePhaseBgm } from "./hooks/usePhaseBgm";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LobbyRoute />} />
        <Route path="/games/:gameId" element={<GameRoute />} />
        <Route path="/admin/login" element={<AdminLoginRoute />} />
        <Route path="/admin" element={<AdminShellRoute />}>
          <Route index element={<AdminDashboardRoute />} />
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
  const store = useGameStore();

  useEffect(() => {
    Promise.all([fetchBoards(), fetchAgents()])
      .then(([boardData, agentData]) => {
        setBoards(boardData);
        setAgents(agentData);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "加载大厅失败"));
  }, []);

  // Wrap createGame to capture room_token
  async function handleCreateGame(payload: CreateGameRequest): Promise<Pick<GameStateDto, "game_id">> {
    const game = await createGame(payload);
    // Bind room token to the created game before routing, so GameRoute can
    // restore it after reset() + loadGame(gameId).
    if (game.room_token) {
      store.rememberRoomToken(game.game_id, game.room_token);
    }
    return game;
  }

  if (error) {
    return <StatusScreen title="大厅加载失败" detail={error} />;
  }
  if (boards.length === 0 || agents.length === 0) {
    return <StatusScreen title="正在整理牌桌" detail="正在读取后端板子和 AI 玩家。" />;
  }
  return <LobbyPage boards={boards} agents={agents} createGame={handleCreateGame} />;
}

function GameRoute() {
  const { gameId } = useParams();
  const store = useGameStore();

  // Initial game load
  useEffect(() => {
    if (!gameId) return;
    store.reset();
    store.loadGame(gameId);
  }, [gameId]);

  // SSE subscription
  useEffect(() => {
    if (!gameId || !store.game?.human_player_id) return;

    const source = subscribeGameStream(gameId, {
      playerId: store.game.human_player_id,
      onEvent: (event) => {
        store.applySseEvent(event);
      },
      onError: () => {
        store.loadGame(gameId);
      }
    });

    return () => source.close();
  }, [gameId, store.game?.human_player_id]);

  // TTS audio playback for AI speeches
  useTtsPlayback(gameId);
  usePhaseBgm(store.game?.phase);

  // Action handler
  async function handleAction(action: SubmitActionInput) {
    if (!gameId) return;
    await store.submitAction(gameId, action);
  }

  if (store.error) {
    return <StatusScreen title="游戏暂时卡住了" detail={store.error} />;
  }
  if (!store.game) {
    return <StatusScreen title="正在进入房间" detail="正在恢复当前游戏状态。" />;
  }
  return <GameTable game={store.game} onSubmitAction={handleAction} pending={store.pending} streamingSpeeches={store.streamingSpeeches} seerResults={store.seerResults} />;
}

function StatusScreen({ title, detail }: { title: string; detail: string }) {
  return (
    <main className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center px-4">
      <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)]">AI WEREWOLF</p>
      <h1 className="text-3xl font-bold">{title}</h1>
      <p className="text-[var(--color-text-dim)]">{detail}</p>
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

function AdminDashboardRoute() {
  const { items: boards } = useAdminData<AdminBoardDto>(fetchAdminBoards);
  const { items: agents } = useAdminData<AdminAgentDto>(fetchAdminAgents);
  const { items: players } = useAdminData<AdminPlayerDto>(fetchAdminPlayers);
  const { items: games } = useAdminData<AdminGameDto>(fetchAdminGames);

  return (
    <AdminDashboardPage
      stats={{
        boardCount: boards.length,
        agentCount: agents.length,
        playerCount: players.length,
        gameCount: games.length,
      }}
    />
  );
}

function AdminPlayersRoute() {
  const { items, error, refresh } = useAdminData<AdminPlayerDto>(fetchAdminPlayers);
  const { items: agents } = useAdminData<AdminAgentDto>(fetchAdminAgents);
  const [showCreate, setShowCreate] = useState(false);
  if (error) {
    return <AdminStatus title="玩家加载失败" detail={error} />;
  }
  return (
    <>
      <AdminPlayersPage
        players={items}
        agents={agents}
        onRefresh={refresh}
        onShowCreate={() => setShowCreate(true)}
        onCreateSubmit={async (payload) => { await createAdminPlayer(payload); }}
        onToggleAi={async (player) => {
          await updateAdminPlayer(player.player_id, { is_ai: !player.is_ai });
          await refresh();
        }}
        onDelete={async (playerId) => {
          await deleteAdminPlayer(playerId);
          await refresh();
        }}
      />
      <PlayerFormModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={async (values) => {
          await createAdminPlayer(values);
          await refresh();
        }}
        agents={agents}
      />
    </>
  );
}

function AdminAgentsRoute() {
  const { items, error, refresh } = useAdminData<AdminAgentDto>(fetchAdminAgents);
  const { items: providers } = useAdminData<AdminLlmProviderDto>(fetchAdminLlmProviders);
  const [showCreate, setShowCreate] = useState(false);
  if (error) {
    return <AdminStatus title="AI 加载失败" detail={error} />;
  }
  return (
    <>
      <AdminAgentsPage
        agents={items}
        onRefresh={refresh}
        onShowCreate={() => setShowCreate(true)}
        onCreateSubmit={async (values) => {
          await createAdminAgent(values);
        }}
        onUpdateSubmit={async (agentId, values) => {
          await updateAdminAgent(agentId, values);
        }}
        onToggleEnabled={async (agent) => {
          await updateAdminAgent(agent.agent_id, { enabled: !agent.enabled });
          await refresh();
        }}
        onDelete={async (agentId) => {
          await deleteAdminAgent(agentId);
          await refresh();
        }}
        providers={providers}
      />
      <AgentFormModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={async (values) => {
          await createAdminAgent(values);
          await refresh();
          return {};
        }}
        providers={providers.map((p) => ({
          provider_id: p.provider_id,
          name: p.model_name ? `${p.provider_id} (${p.model_name})` : p.provider_id,
        }))}
      />
    </>
  );
}

function AdminBoardsRoute() {
  const { items, error, refresh } = useAdminData<AdminBoardDto>(fetchAdminBoards);
  const { items: roles } = useAdminData<AdminRoleDto>(() => seedAdminRoles().then(() => fetchAdminRoles()));
  const [showCreate, setShowCreate] = useState(false);

  if (error) {
    return <AdminStatus title="板子加载失败" detail={error} />;
  }
  return (
    <>
      <AdminBoardsPage
        boards={items}
        onRefresh={refresh}
        onShowCreate={() => setShowCreate(true)}
        onToggleEnabled={async (board) => {
          await updateAdminBoard(board.board_id, { enabled: !board.enabled });
          await refresh();
        }}
        onReplaceRoles={async (boardId, boardRoles) => {
          await replaceAdminBoardRoles(boardId, boardRoles);
          await refresh();
        }}
        onDelete={async (boardId) => {
          await deleteAdminBoard(boardId);
          await refresh();
        }}
      />
      <BoardCreateModal
        isOpen={showCreate}
        roles={roles}
        onCreateComplete={async (payload) => {
          await createAdminBoardComplete(payload);
          await refresh();
          return {} as AdminBoardDto;
        }}
        onClose={() => setShowCreate(false)}
      />
    </>
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
