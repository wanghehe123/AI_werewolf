export interface BoardRoleCount {
  role_key: string;
  count: number;
}

export interface BoardConfig {
  board_id: string;
  name: string;
  roles: BoardRoleCount[];
  sheriff_enabled: boolean;
  speech_rule: string;
  vote_rule: string;
  win_condition: string;
  enabled: boolean;
  player_count: number;
}

export interface AgentProfile {
  agent_id: string;
  name: string;
  avatar_url: string | null;
  avatar_prompt: string | null;
  persona: string;
  speech_style: string;
  reasoning_level: number;
  deception_level: number;
  aggression_level: number;
  cooperation_level: number;
  risk_preference: "conservative" | "balanced" | "aggressive";
  memory_style: string;
  enabled: boolean;
}

export type GamePhase =
  | "setup"
  | "night"
  | "day_announcement"
  | "sheriff_election"
  | "sheriff_speech"
  | "day_speech"
  | "exile_vote"
  | "last_words"
  | "game_over";

export interface PlayerStateDto {
  player_id: string;
  agent_id: string | null;
  seat: number;
  role_key: string | null;
  alive: boolean;
  is_human: boolean;
  sheriff: boolean;
  display_name: string;
  avatar_url: string | null;
  model_provider_id?: string;
  speaking: boolean;
  voted: boolean;
}

export interface GameEventDto {
  event_type: string;
  actor_id: string | null;
  target_id: string | null;
  payload: {
    message?: string;
    [key: string]: unknown;
  };
  public: boolean;
}

export interface PlayerActionOptionDto {
  action_type: string;
  label: string;
}

export interface GameStateDto {
  game_id: string;
  board_id: string;
  phase: GamePhase;
  day_count: number;
  human_player_id: string;
  current_turn_player_id: string | null;
  players: PlayerStateDto[];
  winner: string | null;
  public_events: GameEventDto[];
  allowed_actions: PlayerActionOptionDto[];
}

export interface CreateGameRequest {
  board_id: string;
  human_player_id: string;
  agent_ids: string[];
}

export interface SubmitActionInput {
  action_type: string;
  target_player_id?: string | null;
  content?: string | null;
}
