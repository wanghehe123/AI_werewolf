import type { AgentProfile, BoardConfig, CreateGameRequest, GameStateDto, SubmitActionInput } from "./types";

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
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      message = body.detail ?? message;
    } catch {
      // Keep the HTTP status text when the backend does not return JSON.
    }
    throw new ApiError(response.status, message);
  }
  return (await response.json()) as T;
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
