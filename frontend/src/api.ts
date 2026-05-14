import type {
  AdminAgentDto,
  AdminBoardDto,
  AdminGameDto,
  AdminPlayerDto,
  AdminRoleDto,
  AdminSessionDto,
  AgentProfile,
  BoardConfig,
  CreateGameRequest,
  GameStateDto,
  SubmitActionInput
} from "./types";

const defaultBaseUrl = "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function apiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? defaultBaseUrl;
}

async function requestJson<T>(path: string, init?: RequestInit, baseUrl = apiBaseUrl()): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, init);
  let body: { code?: number; message?: string; detail?: string; data?: T } | null = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    const message = body?.message ?? body?.detail ?? response.statusText;
    throw new ApiError(response.status, message);
  }
  if (body && typeof body.code === "number" && body.code !== 0) {
    throw new ApiError(body.code, body.message ?? "请求失败");
  }
  return body?.data as T;
}

function adminInit(init?: RequestInit): RequestInit {
  return { ...init, credentials: "include" };
}

export function fetchBoards(baseUrl?: string): Promise<BoardConfig[]> {
  return requestJson<BoardConfig[]>("/boards", undefined, baseUrl);
}

export function fetchAgents(baseUrl?: string): Promise<AgentProfile[]> {
  return requestJson<AgentProfile[]>("/agents", undefined, baseUrl);
}

export function createGame(payload: CreateGameRequest, baseUrl?: string): Promise<GameStateDto> {
  return requestJson<GameStateDto>(
    "/games",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    },
    baseUrl
  );
}

export function fetchGame(gameId: string, baseUrl?: string): Promise<GameStateDto> {
  return requestJson<GameStateDto>(`/games/${gameId}`, undefined, baseUrl);
}

export function submitGameAction(gameId: string, payload: SubmitActionInput, baseUrl?: string): Promise<GameStateDto> {
  return requestJson<GameStateDto>(
    `/games/${gameId}/actions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actor_player_id: "human",
        client_action_id: `web-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        ...payload
      })
    },
    baseUrl
  );
}

export function adminLogin(username: string, password: string, baseUrl?: string): Promise<{ session_id: string }> {
  const params = new URLSearchParams({ username, password });
  return requestJson<{ session_id: string }>(`/admin/login?${params.toString()}`, adminInit({ method: "POST" }), baseUrl);
}

export function adminLogout(baseUrl?: string): Promise<null> {
  return requestJson<null>("/admin/logout", adminInit({ method: "POST" }), baseUrl);
}

export function fetchAdminSession(baseUrl?: string): Promise<AdminSessionDto> {
  return requestJson<AdminSessionDto>("/admin/session", adminInit(), baseUrl);
}

export function fetchAdminPlayers(baseUrl?: string): Promise<AdminPlayerDto[]> {
  return requestJson<AdminPlayerDto[]>("/admin/players", adminInit(), baseUrl);
}

export function createAdminPlayer(payload: { name: string; is_ai: boolean; agent_id?: string | null }, baseUrl?: string): Promise<AdminPlayerDto> {
  return requestJson<AdminPlayerDto>(
    "/admin/players",
    adminInit({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
    baseUrl
  );
}

export function fetchAdminAgents(baseUrl?: string): Promise<AdminAgentDto[]> {
  return requestJson<AdminAgentDto[]>("/admin/agents", adminInit(), baseUrl);
}

export function createAdminAgent(payload: Partial<AdminAgentDto> & { name: string; persona: string; speech_style: string }, baseUrl?: string): Promise<AdminAgentDto> {
  return requestJson<AdminAgentDto>(
    "/admin/agents",
    adminInit({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
    baseUrl
  );
}

export function fetchAdminBoards(baseUrl?: string): Promise<AdminBoardDto[]> {
  return requestJson<AdminBoardDto[]>("/admin/boards", adminInit(), baseUrl);
}

export function createAdminBoard(payload: Omit<AdminBoardDto, "board_id" | "roles" | "created_at">, baseUrl?: string): Promise<AdminBoardDto> {
  return requestJson<AdminBoardDto>(
    "/admin/boards",
    adminInit({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
    baseUrl
  );
}

export function replaceAdminBoardRoles(boardId: string, roles: Array<{ role_key: string; count: number }>, baseUrl?: string): Promise<AdminBoardDto["roles"]> {
  return requestJson<AdminBoardDto["roles"]>(
    `/admin/boards/${boardId}/roles`,
    adminInit({ method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ roles }) }),
    baseUrl
  );
}

export function fetchAdminRoles(baseUrl?: string): Promise<AdminRoleDto[]> {
  return requestJson<AdminRoleDto[]>("/admin/roles", adminInit(), baseUrl);
}

export function seedAdminRoles(baseUrl?: string): Promise<AdminRoleDto[]> {
  return requestJson<AdminRoleDto[]>("/admin/roles/seed", adminInit({ method: "POST" }), baseUrl);
}

export function fetchAdminGames(baseUrl?: string): Promise<AdminGameDto[]> {
  return requestJson<AdminGameDto[]>("/admin/games", adminInit(), baseUrl);
}
