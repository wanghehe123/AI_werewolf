import { useEffect, useRef } from "react";
import { AudioQueue, type QueueItem } from "../audio/AudioQueue";
import { StreamPlayer } from "../audio/StreamPlayer";
import { fetchTtsAudio } from "../services/tts";
import { useGameStore } from "../stores/gameStore";

export function useTtsPlayback(gameId: string | undefined) {
  const playerRef = useRef<StreamPlayer | null>(null);
  const queueRef = useRef<AudioQueue | null>(null);
  const requestedAnnouncementIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!gameId) return;

    const player = new StreamPlayer();
    const queue = new AudioQueue(player);
    const unlockAudio = () => {
      void player.unlock().catch(() => undefined);
    };
    window.addEventListener("pointerdown", unlockAudio, { passive: true });
    window.addEventListener("keydown", unlockAudio);
    queue.onItemStart = () => {
      window.dispatchEvent(new CustomEvent("werewolf-voice-playback", { detail: { playing: true } }));
    };
    queue.onItemEnd = (item) => {
      if (item.announcementId) {
        useGameStore.getState().removeAudioAnnouncement(item.announcementId);
      }
      window.dispatchEvent(new CustomEvent("werewolf-voice-playback", { detail: { playing: false } }));
    };
    playerRef.current = player;
    queueRef.current = queue;

    return () => {
      window.removeEventListener("pointerdown", unlockAudio);
      window.removeEventListener("keydown", unlockAudio);
      player.destroy();
      requestedAnnouncementIdsRef.current.clear();
      playerRef.current = null;
      queueRef.current = null;
    };
  }, [gameId]);

  useEffect(() => {
    if (!gameId) return;

    const unsub = useGameStore.subscribe((state, prev) => {
      const newAnnouncements = state.audioAnnouncements.filter(
        (announcement) =>
          !prev.audioAnnouncements.some((previous) => previous.id === announcement.id) &&
          !requestedAnnouncementIdsRef.current.has(announcement.id)
      );

      for (const announcement of newAnnouncements) {
        requestedAnnouncementIdsRef.current.add(announcement.id);
        fetchTtsAudio(gameId, { text: announcement.text, voice: announcement.voice })
          .then((audioData) => {
            const item: QueueItem = {
              playerId: announcement.actorId ?? "system",
              label: announcement.label ?? (announcement.kind === "system" ? "系统播报" : "玩家发言"),
              audioData,
              fallbackText: announcement.text,
              announcementId: announcement.id,
              kind: announcement.kind,
            };
            queueRef.current?.enqueue(item);
          })
          .catch((err) => {
            console.warn("TTS fetch failed, skipping audio:", err);
            queueRef.current?.enqueue({
              playerId: announcement.actorId ?? "system",
              label: announcement.label ?? (announcement.kind === "system" ? "系统播报" : "玩家发言"),
              fallbackText: announcement.text,
              announcementId: announcement.id,
              kind: announcement.kind,
            });
          });
      }
    });

    return unsub;
  }, [gameId]);
}
