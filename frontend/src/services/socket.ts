import { io, type Socket } from "socket.io-client";
import { apiBaseUrl } from "../api";
import type { GameStreamEventDto } from "../types";

export interface GameSocketOptions {
  gameId: string;
  playerId: string;
  onEvent: (event: GameStreamEventDto) => void;
  onSnapshot?: (state: unknown) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (message: string) => void;
}

export function connectGameSocket(options: GameSocketOptions): Socket {
  const baseUrl = apiBaseUrl();
  const socket = io(baseUrl, {
    path: "/socket.io",
    transports: ["websocket"],  // prefer WebSocket for performance
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
  });

  socket.on("connect", () => {
    socket.emit("join_game", {
      game_id: options.gameId,
      player_id: options.playerId
    });
    options.onConnect?.();
  });

  socket.on("disconnect", () => {
    options.onDisconnect?.();
  });

  socket.on("state_snapshot", (data: Record<string, unknown>) => {
    if (data.game_state) {
      options.onSnapshot?.(data.game_state);
    }
    options.onEvent({
      event_id: data.event_id as string ?? "",
      event_type: "state_snapshot",
      game_id: options.gameId,
      phase: (data as Record<string, unknown>).phase as GameStreamEventDto["phase"] ?? "setup",
      day_count: (data as Record<string, unknown>).day_count as number ?? 0,
      visibility: "self",
      actor_id: null,
      target_id: options.playerId,
      payload: { game_state: data.game_state as Record<string, unknown> },
      created_at: null,
    });
  });

  socket.on("speech_delta", (data: Record<string, unknown>) => {
    options.onEvent(data as unknown as GameStreamEventDto);
  });

  socket.on("speech_completed", (data: Record<string, unknown>) => {
    options.onEvent(data as unknown as GameStreamEventDto);
  });

  socket.on("private_info", (data: Record<string, unknown>) => {
    options.onEvent(data as unknown as GameStreamEventDto);
  });

  socket.on("phase_changed", (data: Record<string, unknown>) => {
    options.onEvent(data as unknown as GameStreamEventDto);
  });

  socket.on("night_result", (data: Record<string, unknown>) => {
    options.onEvent(data as unknown as GameStreamEventDto);
  });

  socket.on("error", (data: { message?: string }) => {
    options.onError?.(data.message ?? "Socket error");
  });

  return socket;
}

export function emitPlayerAction(
  socket: Socket,
  action: { action_type: string; target_player_id?: string | null; content?: string | null },
  actorPlayerId = "human"
): void {
  socket.emit("player_action", {
    actor_player_id: actorPlayerId,
    action_type: action.action_type,
    target_player_id: action.target_player_id ?? undefined,
    content: action.content ?? undefined,
    client_action_id: `sio-${Date.now()}-${Math.random().toString(16).slice(2)}`,
  });
}

export function disconnectGameSocket(socket: Socket): void {
  socket.disconnect();
}
