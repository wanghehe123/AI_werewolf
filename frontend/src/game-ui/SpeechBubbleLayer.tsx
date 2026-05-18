import { AnimatePresence, motion } from "framer-motion";
import type { StreamingSpeechDto } from "../types";
import type { PlayerVisualState } from "./gameVisualTypes";

interface SpeechBubbleLayerProps {
  players: PlayerVisualState[];
  streamingSpeeches: Record<string, StreamingSpeechDto>;
}

export function SpeechBubbleLayer({ players, streamingSpeeches }: SpeechBubbleLayerProps) {
  const entries = Object.entries(streamingSpeeches).filter(([, v]) => v.speech.trim().length > 0);

  if (entries.length === 0) return null;

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <AnimatePresence>
        {entries.map(([playerId, speech]) => {
          const player = players.find((p) => p.playerId === playerId);
          if (!player) return null;

          return (
            <motion.div
              key={playerId}
              className="absolute max-w-[220px] p-3 rounded-xl bg-[var(--color-warm-card)]/95 border border-[var(--color-gold)]/30 shadow-lg text-sm text-[var(--color-text)]"
              style={{
                top: player.seat <= 3 ? "20%" : "55%",
                left: player.seat <= 2 ? "8%" : player.seat <= 4 ? "38%" : "68%",
              }}
              initial={{ opacity: 0, scale: 0.9, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -8 }}
              transition={{ duration: 0.3 }}
            >
              <p className="text-xs font-semibold text-[var(--color-gold)] mb-1">{speech.label}</p>
              <p className="max-h-[80px] overflow-y-auto text-xs leading-relaxed">{speech.speech}</p>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
