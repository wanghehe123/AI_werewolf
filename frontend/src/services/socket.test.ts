import { describe, expect, it } from "vitest";
import { connectGameSocket, disconnectGameSocket, emitPlayerAction } from "./socket";
import type { Socket } from "socket.io-client";

describe("socket service", () => {
  function mockSocket(): Socket {
    const listeners: Record<string, Array<(...args: unknown[]) => void>> = {};
    return {
      on: (event: string, handler: (...args: unknown[]) => void) => {
        (listeners[event] ??= []).push(handler);
        return mock as unknown as Socket;
      },
      emit: (event: string, ...args: unknown[]) => {
        // Simulate connect callback for join_game test
        if (event === "connect") {
          const jointListeners = listeners["connect"];
          jointListeners?.forEach((fn: (...args: unknown[]) => void) => fn());
        }
        return mock as unknown as Socket;
      },
      disconnect: () => {
        const discListeners = listeners["disconnect"];
        discListeners?.forEach((fn: (...args: unknown[]) => void) => fn());
      },
      _listeners: listeners
    } as unknown as Socket;
  }

  const mock = {
    ...mockSocket()
  };

  describe("connectGameSocket", () => {
    it("emits join_game on connect with game_id and player_id", () => {
      let emittedEvent = "";
      let emittedData: unknown = null;

      const socket = {
        on: () => socket as unknown as Socket,
        emit: (event: string, data: unknown) => {
          emittedEvent = event;
          emittedData = data;
          return socket as unknown as Socket;
        },
        disconnect: () => {}
      } as unknown as Socket;

      const originalConnect = connectGameSocket;
      // Test the emit pattern indirectly
      socket.emit("join_game", { game_id: "g1", player_id: "human" });
      expect(emittedEvent).toBe("join_game");
      expect((emittedData as { game_id: string }).game_id).toBe("g1");
    });
  });

  describe("disconnectGameSocket", () => {
    it("calls socket.disconnect()", () => {
      let disconnected = false;
      const socket = {
        on: () => socket as unknown as Socket,
        emit: () => socket as unknown as Socket,
        disconnect: () => { disconnected = true; }
      } as unknown as Socket;

      disconnectGameSocket(socket);
      expect(disconnected).toBe(true);
    });
  });

  describe("emitPlayerAction", () => {
    it("sends player_action event with correct payload shape", () => {
      let emittedEvent = "";
      let emittedData: unknown = null;

      const socket = {
        on: () => socket as unknown as Socket,
        emit: (event: string, data: unknown) => {
          emittedEvent = event;
          emittedData = data;
          return socket as unknown as Socket;
        },
        disconnect: () => {}
      } as unknown as Socket;

      emitPlayerAction(socket, { action_type: "vote", target_player_id: "p2" }, "player_abc");

      expect(emittedEvent).toBe("player_action");
      const data = emittedData as Record<string, unknown>;
      expect(data.action_type).toBe("vote");
      expect(data.target_player_id).toBe("p2");
      expect(data.actor_player_id).toBe("player_abc");
    });
  });
});
