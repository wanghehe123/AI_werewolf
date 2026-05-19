import type { GameStateDto, GameEventDto, SeerCheckResult } from "../types";
import type { PlayerVisualState, VisualEventItem, ActionDockKind, EventFilterKind } from "./gameVisualTypes";

/* ── Role labels ───────────────────────────────────────── */

export function roleLabel(roleKey: string): string {
  const labels: Record<string, string> = {
    werewolf: "狼人",
    seer: "预言家",
    witch: "女巫",
    hunter: "猎人",
    villager: "村民",
  };
  return labels[roleKey] ?? roleKey;
}

/* ── Phase labels ──────────────────────────────────────── */

export function phaseLabel(phase: string): string {
  const labels: Record<string, string> = {
    setup: "准备开局",
    night: "夜晚行动",
    day_announcement: "昨夜信息",
    sheriff_election: "警长竞选",
    sheriff_speech: "竞选发言",
    day_speech: "白天发言",
    exile_vote: "放逐投票",
    last_words: "遗言",
    game_over: "游戏复盘",
  };
  return labels[phase] ?? phase;
}

/* ── Event labels (human-readable) ─────────────────────── */

export function eventLabel(eventType: string): string {
  const labels: Record<string, string> = {
    phase_changed: "阶段推进",
    night_step_started: "夜晚行动",
    night_step_finished: "夜晚行动",
    sheriff_election: "警长竞选",
    sheriff_election_speech: "竞选发言",
    sheriff_vote: "警长投票",
    sheriff_elected: "警长结果",
    sheriff_tie: "警长结果",
    speech_completed: "玩家发言",
    speech_delta: "实时发言",
    current_speaker_changed: "轮到发言",
    night_result: "昨夜结果",
    private_info: "私密信息",
    game_created: "房间创建",
    game_end: "游戏结束",
    role_reveal: "身份揭晓",
    last_words: "遗言",
    exile: "放逐结果",
    speech: "玩家发言",
  };
  return labels[eventType] ?? "游戏事件";
}

/* ── Event message ─────────────────────────────────────── */

export function eventMessage(event: GameEventDto): string {
  return event.payload.message ?? "";
}

/* ── Selectable targets ────────────────────────────────── */

export function selectablePlayerIds(game: GameStateDto): string[] {
  const fromOptions = game.allowed_actions.flatMap(
    (action) => action.target_options?.map((t) => t.player_id) ?? []
  );
  if (fromOptions.length > 0) return fromOptions;

  // Fallback: actions that need a target but lack target_options
  // - explicit requires_target (night actions like seer_check)
  // - implicit: vote action has no requires_target but needs a target
  const needsTarget = game.allowed_actions.some(
    (a) => (a.requires_target && !a.target_options?.length) || a.action_type === "vote"
  );
  if (needsTarget) {
    return game.players
      .filter((p) => p.alive && !p.is_human)
      .map((p) => p.player_id);
  }

  return [];
}

/* ── Current action kind ───────────────────────────────── */

export function currentActionKind(game: GameStateDto): ActionDockKind {
  const action = game.allowed_actions[0];
  if (!action) return "observer";

  if (game.phase === "sheriff_election") return "sheriff_election";
  if (game.phase === "sheriff_speech" && action.action_type === "speech") return "sheriff_speech";
  if (game.phase === "sheriff_speech" && (action.action_type === "vote" || action.action_type === "abstain")) return "sheriff_vote";
  if (action.action_type === "speech") return "speech";
  if (action.action_type === "vote") return "vote";
  if (action.action_type === "abstain") return "vote";
  if (action.action_type === "night_start") return "night_start";
  if (action.action_type === "witch_save" || action.action_type === "witch_poison" || action.action_type === "no_action") return "witch_action";
  if (action.action_type === "start_game" || action.action_type === "continue") return "continue";
  if (action.requires_target) return "night_target";

  return "continue";
}

/* ── Derive player visual states ───────────────────────── */

export function derivePlayerVisualStates(
  game: GameStateDto,
  selectedTargetId: string | null,
  seerResults: Record<string, SeerCheckResult>
): PlayerVisualState[] {
  const selectableIds = selectablePlayerIds(game);

  // Detect sheriff candidates from public events
  const candidateIds = new Set<string>();
  for (const event of game.public_events) {
    if (event.event_type === "sheriff_election" && event.actor_id) {
      // Only count players who ARE running (not skipping/不参加)
      const msg = event.payload.message ?? "";
      if (msg.includes("参加警长竞选") && !msg.includes("不参加")) {
        candidateIds.add(event.actor_id);
      }
    }
  }

  return game.players.map((player) => {
    const isSelf = player.player_id === game.human_player_id;
    const selectable = selectableIds.includes(player.player_id);
    const selected = player.player_id === selectedTargetId;
    const speaking = player.speaking;
    const alive = player.alive;

    let visualTone: PlayerVisualState["visualTone"] = "normal";
    if (!alive) visualTone = "dead";
    else if (speaking) visualTone = "speaking";
    else if (selectable) visualTone = selected ? "selected" : "selectable";
    else if (isSelf) visualTone = "self";

    const seerResult = seerResults[player.player_id];

    return {
      playerId: player.player_id,
      seat: player.seat,
      displayName: player.display_name,
      avatarUrl: player.avatar_url,
      roleLabel: player.role_key ? roleLabel(player.role_key) : undefined,
      alive,
      isSelf,
      isSheriff: player.sheriff,
      isSheriffCandidate: candidateIds.has(player.player_id) && alive,
      speaking,
      voted: player.voted,
      selectable,
      selected,
      checkedCamp: seerResult?.camp,
      visualTone,
    };
  });
}

/* ── Classify event filter ─────────────────────────────── */

export function classifyEventFilter(eventType: string): EventFilterKind {
  const speechTypes = new Set([
    "speech_completed",
    "speech_delta",
    "speech",
    "last_words",
    "sheriff_election_speech",
  ]);
  const actionTypes = new Set([
    "phase_changed",
    "night_step_started",
    "night_step_finished",
    "night_result",
    "exile",
    "game_end",
    "game_created",
    "sheriff_election",
    "sheriff_vote",
    "sheriff_elected",
    "sheriff_tie",
  ]);

  if (speechTypes.has(eventType)) return "speech";
  if (actionTypes.has(eventType)) return "action";
  return "all";
}

/* ── Build visual events ───────────────────────────────── */

export function buildVisualEvents(events: GameEventDto[]): VisualEventItem[] {
  return events.map((event, index) => ({
    id: `${event.event_type}-${index}`,
    eventType: event.event_type,
    label: eventLabel(event.event_type),
    message: eventMessage(event),
    timestamp: undefined,
    isLatest: index === events.length - 1,
    filter: classifyEventFilter(event.event_type),
  }));
}
