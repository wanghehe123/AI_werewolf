import { motion } from "framer-motion";
import { phaseLabel } from "./gameVisuals";
import { VoteTally } from "./VoteTally";
import type { GameStateDto } from "../types";

interface TableCenterProps {
  game: GameStateDto;
  latestEventMessage?: string;
}

export function TableCenter({ game, latestEventMessage }: TableCenterProps) {
  const isNight = game.phase === "night";
  const isGameOver = game.phase === "game_over";
  const isLastWords = game.phase === "last_words";

  const centerText = isNight
    ? "天黑请闭眼"
    : isGameOver
      ? (game.winner === "wolves" ? "狼人阵营获胜" : "好人阵营获胜")
      : isLastWords
        ? "遗言"
        : phaseLabel(game.phase);

  const speakingPlayer = game.players.find((p) => p.speaking);

  return (
    <div className={`
      relative flex flex-col items-center justify-center rounded-2xl p-6 min-h-[160px]
      max-h-[min(34vh,360px)] min-w-0 overflow-hidden
      ${isNight
        ? "bg-[var(--color-night-fog)]/50 border border-[var(--color-blue-night)]/20"
        : "bg-[var(--color-table-felt)] border border-[var(--color-table-edge)]/40"
      }
      transition-colors duration-700
    `}>
      {/* Phase title */}
      <motion.h2
        className="text-lg font-bold text-center mb-2"
        key={game.phase}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        {centerText}
      </motion.h2>

      {/* Day count */}
      <p className="text-xs text-[var(--color-text-muted)] mb-3">第 {game.day_count} 天</p>

      {/* Speaking indicator */}
      {speakingPlayer && (
        <motion.div
          className="text-sm text-[var(--color-gold)] flex items-center gap-2"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          key={speakingPlayer.player_id}
        >
          <span className="w-2 h-2 rounded-full bg-[var(--color-gold)] animate-[breathing_1.5s_ease-in-out_infinite]" />
          正在发言：{speakingPlayer.seat}号 {speakingPlayer.display_name}
        </motion.div>
      )}

      {/* Latest event */}
      {!speakingPlayer && latestEventMessage && (
        <motion.div
          aria-label="当前事件摘要"
          className="min-h-0 max-h-[min(24vh,220px)] overflow-y-auto px-1 text-sm leading-relaxed text-[var(--color-text-dim)] text-center [scrollbar-gutter:stable]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <p>{latestEventMessage}</p>
        </motion.div>
      )}

      {/* Vote tally during voting phases */}
      <VoteTally game={game} />

      {/* Game over winner display */}
      {isGameOver && game.winner && (
        <motion.div
          className={`mt-4 px-6 py-3 rounded-xl text-center ${
            game.winner === "wolves"
              ? "bg-[var(--color-red-bg)] border border-red-800/40"
              : "bg-[var(--color-green-bg)] border border-green-800/40"
          }`}
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 200 }}
        >
          <p className="font-bold text-lg">
            {game.winner === "wolves" ? "狼人阵营" : "好人阵营"} 获得胜利
          </p>
        </motion.div>
      )}

      {/* Night atmosphere */}
      {isNight && (
        <div className="absolute inset-0 rounded-2xl pointer-events-none animate-[breathing_4s_ease-in-out_infinite] bg-gradient-to-b from-[var(--color-blue-night)]/5 to-transparent" />
      )}
    </div>
  );
}
