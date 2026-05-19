import { useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { GameStateDto } from "../types";

interface VoteTallyProps {
  game: GameStateDto;
}

interface VoteEntry {
  voterId: string;
  voterLabel: string;
  targetId: string | null;
  targetLabel: string | null;
}

interface TallyItem {
  targetId: string;
  targetLabel: string;
  count: number;
  voters: string[];
}

function currentVoteWindowStart(game: GameStateDto): number {
  let resetIndex = 0;
  for (let i = game.public_events.length - 1; i >= 0; i--) {
    const e = game.public_events[i];
    const message = e.payload.message ?? "";
    if (game.phase === "sheriff_speech" && e.event_type === "phase_changed" && message.includes("竞选发言结束")) {
      resetIndex = i;
      break;
    }
    if (game.phase === "exile_vote" && e.event_type === "phase_changed" && message.includes("放逐投票")) {
      resetIndex = i;
      break;
    }
  }
  return resetIndex;
}

/**
 * Extract vote entries from public_events for the current voting phase.
 * Abstentions count as voted, but do not add a target tally bar.
 */
function extractVoteEntries(game: GameStateDto): VoteEntry[] {
  const entries: VoteEntry[] = [];
  const playerMap = new Map(game.players.map((p) => [p.player_id, p]));
  const resetIndex = currentVoteWindowStart(game);

  for (let i = resetIndex; i < game.public_events.length; i++) {
    const event = game.public_events[i];
    if (event.event_type === "exile" || event.event_type === "sheriff_elected" || event.event_type === "sheriff_tie") break;
    const isSheriffVote = event.event_type === "sheriff_vote";
    const isExileVote = event.event_type === "vote";
    if (!isSheriffVote && !isExileVote) continue;

    const voterId = event.actor_id;
    const targetId = event.target_id;
    if (!voterId) continue;

    const voter = playerMap.get(voterId);
    const target = targetId ? playerMap.get(targetId) : null;
    if (!voter || (targetId && !target)) continue;

    // Only first occurrence per voter
    if (entries.some((e) => e.voterId === voterId)) continue;

    entries.push({
      voterId,
      voterLabel: `${voter.seat}号 ${voter.display_name}`,
      targetId: targetId ?? null,
      targetLabel: target ? `${target.seat}号 ${target.display_name}` : null,
    });
  }

  return entries;
}

/**
 * Compute tally items grouped by target.
 */
function computeTally(entries: VoteEntry[], game: GameStateDto): TallyItem[] {
  const tallyMap = new Map<string, { label: string; count: number; voters: string[] }>();

  for (const entry of entries) {
    if (!entry.targetId || !entry.targetLabel) continue;
    const existing = tallyMap.get(entry.targetId);
    if (existing) {
      existing.count += 1;
      existing.voters.push(entry.voterLabel);
    } else {
      tallyMap.set(entry.targetId, {
        label: entry.targetLabel,
        count: 1,
        voters: [entry.voterLabel],
      });
    }
  }

  return Array.from(tallyMap.entries()).map(([targetId, data]) => ({
    targetId,
    targetLabel: data.label,
    count: data.count,
    voters: data.voters,
  }));
}

/**
 * Find sheriff candidates from public_events.
 */
function findCandidates(game: GameStateDto): Set<string> {
  const candidates = new Set<string>();
  for (const event of game.public_events) {
    if (event.event_type === "sheriff_election" && event.actor_id) {
      const message = event.payload.message ?? "";
      if (message.includes("参加警长竞选") && !message.includes("不参加")) {
        candidates.add(event.actor_id);
      }
    }
  }
  return candidates;
}

/**
 * Get the list of voters who haven't voted yet.
 */
function pendingVoters(entries: VoteEntry[], game: GameStateDto): string[] {
  const votedIds = new Set(entries.map((e) => e.voterId));
  const playerMap = new Map(game.players.map((p) => [p.player_id, p]));
  const candidates = findCandidates(game);

  let eligibleIds: string[];
  if (game.phase === "sheriff_speech") {
    // Voters: alive non-candidate players
    eligibleIds = game.players
      .filter((p) => p.alive && !candidates.has(p.player_id))
      .map((p) => p.player_id);
  } else {
    // exile_vote: all alive players
    eligibleIds = game.players
      .filter((p) => p.alive)
      .map((p) => p.player_id);
  }

  return eligibleIds
    .filter((id) => !votedIds.has(id))
    .map((id) => {
      const player = playerMap.get(id);
      return player ? `${player.seat}号 ${player.display_name}` : id;
    });
}

/**
 * Check if exile result has been announced (voting is over).
 */
function voteResolvedInCurrentWindow(game: GameStateDto): boolean {
  const resetIndex = currentVoteWindowStart(game);
  return game.public_events
    .slice(resetIndex)
    .some((e) => e.event_type === "exile" || e.event_type === "sheriff_elected" || e.event_type === "sheriff_tie");
}

export function VoteTally({ game }: VoteTallyProps) {
  const entries = useMemo(() => extractVoteEntries(game), [game.public_events, game.players, game.phase]);
  const tally = useMemo(() => computeTally(entries, game), [entries, game.players]);
  const pending = useMemo(() => pendingVoters(entries, game), [entries, game.public_events, game.players, game.phase]);

  // Show during sheriff_speech when vote events exist (AI voting or human has vote options)
  const sheriffVoteInProgress =
    game.phase === "sheriff_speech" &&
    (entries.length > 0 ||
      game.allowed_actions.some((a) => a.action_type === "vote" || a.action_type === "abstain"));

  // Show during exile_vote while voting is still ongoing
  const exileVoteInProgress =
    game.phase === "exile_vote" && !voteResolvedInCurrentWindow(game);

  if (!sheriffVoteInProgress && !exileVoteInProgress) return null;

  const totalVoted = entries.length;
  const phaseTitle = game.phase === "sheriff_speech" ? "警长投票" : "放逐投票";

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={`${game.phase}-${totalVoted}`}
        className="mt-3 w-full max-h-[220px] overflow-y-auto"
        initial={{ opacity: 0, scaleY: 0.5 }}
        animate={{ opacity: 1, scaleY: 1 }}
        exit={{ opacity: 0, scaleY: 0.5 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
      >
        {/* Title + progress */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-[var(--color-gold)]">
            {phaseTitle}
          </span>
          <motion.span
            className="text-[10px] text-[var(--color-text-dim)]"
            key={totalVoted}
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 0.3 }}
          >
            已投 {totalVoted} 票
          </motion.span>
        </div>

        {/* Tally bars */}
        {tally.length > 0 ? (
          <div className="space-y-1.5">
            {tally
              .sort((a, b) => b.count - a.count)
              .map((item) => (
                <motion.div
                  key={item.targetId}
                  className="flex items-center gap-2"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <span className="text-[11px] w-24 text-right text-[var(--color-text-dim)] truncate">
                    {item.targetLabel}
                  </span>
                  <div className="flex-1 bg-[var(--color-warm-border)]/30 rounded-full h-4 overflow-hidden relative">
                    <motion.div
                      className="h-full rounded-full bg-[var(--color-gold)]/80"
                      animate={{
                        width: `${Math.min((item.count / Math.max(totalVoted, 1)) * 100, 100)}%`,
                      }}
                      transition={{ duration: 0.4, type: "spring", stiffness: 150 }}
                    >
                      <motion.div
                        className="absolute inset-0 rounded-full bg-[var(--color-gold)]/30"
                        animate={{ opacity: [0, 0.3, 0] }}
                        transition={{ duration: 1, repeat: Infinity }}
                      />
                    </motion.div>
                  </div>
                  <motion.span
                    className="text-[11px] font-bold text-[var(--color-gold)] w-5 text-right"
                    key={item.count}
                    animate={{ scale: [1, 1.3, 1] }}
                    transition={{ duration: 0.3 }}
                  >
                    {item.count}
                  </motion.span>
                </motion.div>
              ))}
          </div>
        ) : (
          <motion.p
            className="text-[10px] text-[var(--color-text-muted)] text-center py-2"
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            {totalVoted > 0 ? "暂无目标票型" : "等待投票..."}
          </motion.p>
        )}

        {/* Voter details */}
        {entries.length > 0 && (
          <motion.div
            className="mt-2 text-[10px] text-[var(--color-text-muted)] space-y-0.5"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            {tally.map((item) => (
              <div key={item.targetId}>
                <span className="text-[var(--color-text-dim)]">{item.targetLabel}：</span>
                {item.voters.map((v, i) => (
                  <motion.span
                    key={v}
                    initial={{ opacity: 0, x: -5 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 }}
                  >
                    {v}{i < item.voters.length - 1 ? "、" : ""}
                  </motion.span>
                ))}
              </div>
            ))}
          </motion.div>
        )}

        {/* Pending voters */}
        {pending.length > 0 && (
          <motion.div
            className="mt-1.5 text-[10px] text-[var(--color-text-muted)]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
          >
            <span className="text-[var(--color-text-dim)]">待投票：</span>
            {pending.join("、")}
          </motion.div>
        )}
      </motion.div>
    </AnimatePresence>
  );
}
