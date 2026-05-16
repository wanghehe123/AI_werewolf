import { useEffect, useRef } from "react";

import { bgmUrlForTrack, phaseToBgmTrack } from "../audio/bgm";
import type { GamePhase } from "../types";

const NORMAL_BGM_VOLUME = 0.38;
const DUCKED_BGM_VOLUME = 0.14;

export function usePhaseBgm(phase: GamePhase | undefined) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const unlockedRef = useRef(false);

  useEffect(() => {
    const audio = audioRef.current ?? new Audio();
    audio.loop = true;
    audio.volume = NORMAL_BGM_VOLUME;
    audioRef.current = audio;

    const unlock = () => {
      unlockedRef.current = true;
      void audio.play().catch(() => undefined);
    };

    window.addEventListener("pointerdown", unlock, { once: true });
    window.addEventListener("keydown", unlock, { once: true });

    return () => {
      window.removeEventListener("pointerdown", unlock);
      window.removeEventListener("keydown", unlock);
      audio.pause();
      audioRef.current = null;
    };
  }, []);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const track = phaseToBgmTrack(phase);
    if (!track) {
      audio.pause();
      audio.removeAttribute("src");
      return;
    }

    const nextUrl = bgmUrlForTrack(track);
    if (audio.src !== new URL(nextUrl, window.location.href).href) {
      audio.src = nextUrl;
      audio.currentTime = 0;
    }

    if (unlockedRef.current) {
      void audio.play().catch(() => undefined);
    }
  }, [phase]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onVoicePlayback = (event: Event) => {
      const playing = Boolean((event as CustomEvent<{ playing?: boolean }>).detail?.playing);
      audio.volume = playing ? DUCKED_BGM_VOLUME : NORMAL_BGM_VOLUME;
    };

    window.addEventListener("werewolf-voice-playback", onVoicePlayback);
    return () => window.removeEventListener("werewolf-voice-playback", onVoicePlayback);
  }, []);
}
