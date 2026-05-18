import { motion, AnimatePresence } from "framer-motion";
import type { GameStateDto } from "../types";
import type { SeerCheckResult } from "../types";

interface EffectsLayerProps {
  game: GameStateDto;
  seerOverlay: SeerCheckResult | null;
  onDismissOverlay: () => void;
}

export function EffectsLayer({ game, seerOverlay, onDismissOverlay }: EffectsLayerProps) {
  const isNight = game.phase === "night";
  const isGameOver = game.phase === "game_over";

  return (
    <>
      {/* Night overlay */}
      <AnimatePresence>
        {isNight && (
          <motion.div
            className="fixed inset-0 pointer-events-none z-10 bg-[var(--color-night-fog)]/40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.7 }}
          />
        )}
      </AnimatePresence>

      {/* Dawn sweep effect */}
      {game.phase === "day_announcement" && (
        <div
          className="fixed inset-0 pointer-events-none z-10"
          style={{
            background: "linear-gradient(90deg, transparent 0%, rgba(255,207,122,0.08) 50%, transparent 100%)",
            backgroundSize: "200% 100%",
            animation: "dawn-sweep 1.2s ease-out forwards",
          }}
        />
      )}

      {/* Seer result overlay */}
      <AnimatePresence>
        {seerOverlay && (
          <motion.div
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            onClick={onDismissOverlay}
          >
            <motion.div
              className={`p-8 rounded-2xl text-center min-w-[280px] backdrop-blur ${
                seerOverlay.camp === "good"
                  ? "bg-[var(--color-green-bg)]/90 border-2 border-[var(--color-green-seer)]"
                  : "bg-[var(--color-red-bg)]/90 border-2 border-red-400"
              }`}
              initial={{ scale: 0.5, opacity: 0, rotateY: 90 }}
              animate={{ scale: 1, opacity: 1, rotateY: 0 }}
              exit={{ scale: 0.8, opacity: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 20 }}
              style={{ animation: "card-reveal 0.5s ease-out" }}
            >
              <p className="text-sm text-[var(--color-text-dim)] mb-2">查验结果</p>
              <h2 className="text-2xl font-bold mb-2">{seerOverlay.targetLabel}</h2>
              <p className={`text-lg font-semibold ${seerOverlay.camp === "good" ? "text-[var(--color-green-seer)]" : "text-red-400"}`}>
                {seerOverlay.camp === "good" ? "好人阵营" : "狼人阵营"}
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
