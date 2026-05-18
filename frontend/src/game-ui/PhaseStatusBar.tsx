import { motion } from "framer-motion";
import { phaseLabel } from "./gameVisuals";
import type { GameStateDto } from "../types";

interface PhaseStatusBarProps {
  game: GameStateDto;
}

export function PhaseStatusBar({ game }: PhaseStatusBarProps) {
  const isNight = game.phase === "night";

  return (
    <motion.header
      className={`flex justify-between items-center px-6 py-4 rounded-xl border transition-colors duration-700
        ${isNight
          ? "border-[var(--color-blue-night)]/30 bg-[var(--color-night-fog)]/60"
          : "border-[var(--color-warm-border)] bg-[var(--color-warm-card)]"
        }`}
      key={`${game.phase}-${game.day_count}`}
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, type: "spring", stiffness: 150 }}
    >
      <div>
        <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-1">
          AI WEREWOLF ROOM
        </p>
        <h1 className="text-2xl font-bold">{phaseLabel(game.phase)}</h1>
      </div>
      <div className="flex gap-4 text-sm text-[var(--color-text-dim)]">
        <span>第 {game.day_count} 天</span>
        {game.winner && (
          <span className="text-[var(--color-gold)] font-semibold">
            胜利：{game.winner === "wolves" ? "狼人阵营" : "好人阵营"}
          </span>
        )}
      </div>
    </motion.header>
  );
}
