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

export interface AudioAnnouncement {
  id: string;
  kind: "system" | "speech";
  text: string;
  actorId?: string;
  label?: string;
  voice?: string;
}

export interface GameStreamEventDto {
  event_id: string;
  event_type:
    | "state_snapshot"
    | "phase_changed"
    | "night_step_started"
    | "night_step_finished"
    | "speech_delta"
    | "speech_completed"
    | "current_speaker_changed"
    | "ai_thinking"
    | "private_info"
    | "game_created"
    | "night_result"
    | string;
  game_id: string;
  phase: GamePhase;
  day_count: number;
  visibility: "public" | "self" | "system" | string;
  actor_id: string | null;
  target_id: string | null;
  payload: Record<string, unknown>;
  created_at: string | null;
}

export interface StateSnapshotPayload {
  game_state: GameStateDto;
}

export interface SpeechDeltaPayload {
  player_id: string;
  label: string;
  delta: string;
  speech: string;
}

export interface StreamingSpeechDto {
  label: string;
  speech: string;
}

export interface SeerCheckResult {
  targetPlayerId: string;
  targetLabel: string;
  camp: "good" | "wolf";
}

export interface PrivateInfoPayload {
  message: string;
  subtype?: "witch_kill";
}

export interface PlayerActionOptionDto {
  action_type: string;
  label: string;
  requires_target?: boolean;
  target_options?: Array<{
    player_id: string;
    label: string;
  }>;
  night_kill_info?: {
    target_id: string;
    target_label: string;
    can_save: boolean;
    reason?: string;
  };
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
  human_role_key?: string | null;
}

export interface SubmitActionInput {
  action_type: string;
  target_player_id?: string | null;
  content?: string | null;
}

export interface AdminSessionDto {
  authenticated: boolean;
}

export interface AdminPlayerDto {
  player_id: string;
  name: string;
  is_ai: boolean;
  agent_id: string | null;
  created_at?: string;
}

export interface AdminAgentDto {
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
  default_model_provider_id?: string | null;
  enabled: boolean;
  created_at?: string;
}

export interface AdminBoardRoleDto {
  board_id?: string;
  role_key: string;
  count: number;
}

export interface AdminBoardDto {
  board_id: string;
  name: string;
  description: string | null;
  min_players: number;
  max_players: number;
  sheriff_enabled: boolean;
  enabled: boolean;
  roles: AdminBoardRoleDto[];
  created_at?: string;
}

export interface AdminRoleDto {
  role_key: string;
  name: string;
  faction: string;
  description: string | null;
  night_action: boolean;
  enabled: boolean;
}

export interface AdminGameDto {
  game_id: string;
  board_id: string;
  human_player_id: string;
  phase: string;
  day_count: number;
  winner: string | null;
  players?: Array<{
    player_id: string;
    agent_id: string | null;
    seat: number;
    role_key: string;
    alive: boolean;
    is_human: boolean;
    sheriff: boolean;
    model_provider_id: string;
  }>;
}

export interface AdminLlmProviderDto {
  provider_id: string;
  provider_type: "fake" | "openai_compatible";
  model_name: string;
  base_url?: string | null;
  api_key_env?: string | null;
  temperature: number;
  max_tokens: number;
  timeout: number;
}

export interface AdminRoleModelBindingDto {
  role_key: string;
  provider_id: string;
}

export interface CreateCompleteBoardRequest {
  name: string;
  description?: string | null;
  min_players: number;
  max_players: number;
  sheriff_enabled: boolean;
  enabled: boolean;
  roles: AdminBoardRoleDto[];
}
