import type { GamePhase } from "../types";

import daytimeBgmUrl from "../music/werewolf_daytime.mp3";
import nightBgmUrl from "../music/werewolf_night.mp3";

export type BgmTrack = "day" | "night";

export function phaseToBgmTrack(phase: GamePhase | undefined): BgmTrack | null {
  if (phase === "night") return "night";
  if (
    phase === "day_announcement" ||
    phase === "sheriff_election" ||
    phase === "sheriff_speech" ||
    phase === "day_speech" ||
    phase === "exile_vote" ||
    phase === "last_words"
  ) {
    return "day";
  }
  return null;
}

export function bgmUrlForTrack(track: BgmTrack): string {
  return track === "night" ? nightBgmUrl : daytimeBgmUrl;
}
