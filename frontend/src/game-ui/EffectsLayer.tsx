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
            className="pointer-events-none fixed inset-0 z-10 bg-[#6078d8]/10"
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
            className="fixed inset-0 z-50 flex items-center justify-center bg-[#173057]/30 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            onClick={onDismissOverlay}
          >
            <motion.div
              className={`min-w-[280px] rounded-[28px] p-8 text-center shadow-[0_24px_70px_rgba(83,105,160,0.26)] ${
                seerOverlay.camp === "good"
                  ? "border-2 border-[#9be7bd] bg-[#ecfff4]"
                  : "border-2 border-[#ffb4b4] bg-[#fff0f0]"
              }`}
              initial={{ scale: 0.5, opacity: 0, rotateY: 90 }}
              animate={{ scale: 1, opacity: 1, rotateY: 0 }}
              exit={{ scale: 0.8, opacity: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 20 }}
              style={{ animation: "card-reveal 0.5s ease-out" }}
            >
              <p className="mb-2 text-sm text-[var(--color-wolf-muted)]">查验结果</p>
              <h2 className="mb-2 text-2xl font-black text-[#17213d]">{seerOverlay.targetLabel}</h2>
              <p className={`text-lg font-black ${seerOverlay.camp === "good" ? "text-[#168552]" : "text-[#be3a45]"}`}>
                {seerOverlay.camp === "good" ? "好人阵营" : "狼人阵营"}
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
