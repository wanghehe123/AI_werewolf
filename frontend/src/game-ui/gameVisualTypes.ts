import type { GamePhase } from "../types";

export interface PlayerVisualState {
  playerId: string;
  seat: number;
  displayName: string;
  avatarUrl: string | null;
  roleLabel?: string;
  alive: boolean;
  isSelf: boolean;
  isSheriff: boolean;
  speaking: boolean;
  voted: boolean;
  selectable: boolean;
  selected: boolean;
  checkedCamp?: "good" | "wolf";
  visualTone: "normal" | "self" | "speaking" | "selectable" | "selected" | "dead";
}

export type EventFilterKind = "all" | "speech" | "action";

export interface VisualEventItem {
  id: string;
  eventType: string;
  label: string;
  message: string;
  timestamp?: string;
  isLatest: boolean;
  filter: EventFilterKind;
}

export type ActionDockKind =
  | "none"
  | "speech"
  | "vote"
  | "night_target"
  | "night_start"
  | "witch_action"
  | "continue"
  | "observer";
