import type {
  AdminAgentDto,
  AdminBoardDto,
  AdminGameDto,
  AdminLlmProviderDto,
  AdminPlayerDto,
  AdminRoleModelBindingDto,
  AdminRoleDto,
  AdminSessionDto,
  AgentProfile,
  BoardConfig,
  CreateCompleteBoardRequest,
  CreateGameRequest,
  GameStateDto,
  GameStreamEventDto,
  SubmitActionInput
} from "./types";

const defaultBaseUrl = "http://localhost:8000";

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

export function subscribeGameStream(
  gameId: string,
  options: {
    playerId: string;
    onEvent: (event: GameStreamEventDto) => void;
    onError?: (event: Event) => void;
  },
  baseUrl = apiBaseUrl()
): EventSource {
  const params = new URLSearchParams({ player_id: options.playerId });
  const source = new EventSource(`${baseUrl}/games/${gameId}/stream?${params.toString()}`);
  const eventTypes = [
    "state_snapshot",
    "phase_changed",
    "night_step_started",
    "night_step_finished",
    "speech_delta",
    "speech_completed",
    "current_speaker_changed",
    "ai_thinking",
    "private_info",
    "game_created",
    "night_result",
    "sheriff_election",
    "sheriff_election_speech",
    "sheriff_vote",
    "sheriff_elected",
    "sheriff_tie",
    "vote",
    "exile",
    "last_words",
    "game_end",
    "role_reveal"
  ];

  for (const eventType of eventTypes) {
    source.addEventListener(eventType, (message) => {
      options.onEvent(JSON.parse((message as MessageEvent<string>).data) as GameStreamEventDto);
    });
  }
  if (options.onError) {
    source.onerror = options.onError;
  }
  return source;
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

export function updateAdminPlayer(playerId: string, payload: Partial<AdminPlayerDto>, baseUrl?: string): Promise<AdminPlayerDto> {
  return requestJson<AdminPlayerDto>(
    `/admin/players/${playerId}`,
    adminInit({ method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
    baseUrl
  );
}

export function deleteAdminPlayer(playerId: string, baseUrl?: string): Promise<{ deleted: boolean }> {
  return requestJson<{ deleted: boolean }>(`/admin/players/${playerId}`, adminInit({ method: "DELETE" }), baseUrl);
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

export function updateAdminAgent(agentId: string, payload: Partial<AdminAgentDto>, baseUrl?: string): Promise<AdminAgentDto> {
  return requestJson<AdminAgentDto>(
    `/admin/agents/${agentId}`,
    adminInit({ method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
    baseUrl
  );
}

export function deleteAdminAgent(agentId: string, baseUrl?: string): Promise<{ deleted: boolean }> {
  return requestJson<{ deleted: boolean }>(`/admin/agents/${agentId}`, adminInit({ method: "DELETE" }), baseUrl);
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

export function createAdminBoardComplete(payload: CreateCompleteBoardRequest, baseUrl?: string): Promise<AdminBoardDto> {
  return requestJson<AdminBoardDto>(
    "/admin/boards/complete",
    adminInit({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
    baseUrl
  );
}

export function updateAdminBoard(boardId: string, payload: Partial<AdminBoardDto>, baseUrl?: string): Promise<AdminBoardDto> {
  return requestJson<AdminBoardDto>(
    `/admin/boards/${boardId}`,
    adminInit({ method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
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

export function deleteAdminBoard(boardId: string, baseUrl?: string): Promise<{ deleted: boolean }> {
  return requestJson<{ deleted: boolean }>(`/admin/boards/${boardId}`, adminInit({ method: "DELETE" }), baseUrl);
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

export function fetchAdminLlmProviders(baseUrl?: string): Promise<AdminLlmProviderDto[]> {
  return requestJson<AdminLlmProviderDto[]>("/admin/llm/providers", adminInit(), baseUrl);
}

export function createAdminLlmProvider(payload: AdminLlmProviderDto, baseUrl?: string): Promise<AdminLlmProviderDto> {
  return requestJson<AdminLlmProviderDto>(
    "/admin/llm/providers",
    adminInit({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
    baseUrl
  );
}

export function fetchAdminRoleModelBindings(baseUrl?: string): Promise<AdminRoleModelBindingDto[]> {
  return requestJson<AdminRoleModelBindingDto[]>("/admin/llm/role-bindings", adminInit(), baseUrl);
}

export function createAdminRoleModelBinding(payload: AdminRoleModelBindingDto, baseUrl?: string): Promise<AdminRoleModelBindingDto> {
  return requestJson<AdminRoleModelBindingDto>(
    "/admin/llm/role-bindings",
    adminInit({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
    baseUrl
  );
}
