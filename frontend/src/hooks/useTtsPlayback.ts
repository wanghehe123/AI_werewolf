import { useEffect, useRef } from "react";
import { AudioQueue, type QueueItem } from "../audio/AudioQueue";
import { StreamPlayer } from "../audio/StreamPlayer";
import { fetchTtsAudio } from "../services/tts";
import { useGameStore } from "../stores/gameStore";

export function useTtsPlayback(gameId: string | undefined) {
  const playerRef = useRef<StreamPlayer | null>(null);
  const queueRef = useRef<AudioQueue | null>(null);

  useEffect(() => {
    if (!gameId) return;

    const player = new StreamPlayer();
    const queue = new AudioQueue(player);
    playerRef.current = player;
    queueRef.current = queue;

    return () => {
      player.destroy();
      playerRef.current = null;
      queueRef.current = null;
    };
  }, [gameId]);

  useEffect(() => {
    if (!gameId) return;

    const unsub = useGameStore.subscribe((state, prev) => {
      const game = state.game;
      const prevGame = prev.game;
      if (!game || !prevGame) return;

      const newEvents = game.public_events.slice(prevGame.public_events.length);
      for (const event of newEvents) {
        if (event.event_type === "speech_completed" && event.payload.message) {
          const speechText = event.payload.message;
          const playerId = event.actor_id;
          if (!speechText || !playerId) continue;

          const player = game.players.find((p) => p.player_id === playerId);
          if (!player || player.is_human) continue;

          fetchTtsAudio(gameId, { text: speechText })
            .then((audioData) => {
              const item: QueueItem = {
                playerId,
                label: `${player.seat}号 ${player.display_name}`,
                audioData
              };
              queueRef.current?.enqueue(item);
            })
            .catch((err) => {
              console.warn("TTS fetch failed, skipping audio:", err);
            });
        }
      }
    });

    return unsub;
  }, [gameId]);
}
