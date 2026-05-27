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
      className={`wolf-glass flex items-center justify-between rounded-[32px] px-7 py-5 transition-colors duration-700 ${
        isNight ? "ring-1 ring-[#8295ff]/30" : ""
      }`}
      key={`${game.phase}-${game.day_count}`}
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, type: "spring", stiffness: 150 }}
    >
      <div>
        <p className="mb-1 text-xs font-black uppercase tracking-[0.2em] text-[var(--color-wolf-muted)]">
          房间号：{game.game_id.slice(-6) || "102938"}
        </p>
        <h1 className="text-2xl font-black text-[#17213d]">{phaseLabel(game.phase)}</h1>
      </div>
      <div className="wolf-soft-card flex items-center gap-4 rounded-full px-6 py-3 text-sm font-bold text-[var(--color-wolf-muted)]">
        <span className="text-2xl">{isNight ? "🌙" : "🌤"}</span>
        <span>第 {game.day_count} 天 · {isNight ? "黑夜" : "白天"}</span>
        {game.winner && (
          <span className="font-black text-[var(--color-wolf-blue)]">
            胜利：{game.winner === "wolves" ? "狼人阵营" : "好人阵营"}
          </span>
        )}
      </div>
    </motion.header>
  );
}
