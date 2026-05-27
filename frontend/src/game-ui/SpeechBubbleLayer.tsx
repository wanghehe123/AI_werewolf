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
              className="absolute max-w-[240px] rounded-[20px] border border-[#dfe7f8] bg-white/90 p-3 text-sm text-[#17213d] shadow-[0_16px_40px_rgba(83,105,160,0.18)] backdrop-blur"
              style={{
                top: player.seat <= 3 ? "20%" : "55%",
                left: player.seat <= 2 ? "8%" : player.seat <= 4 ? "38%" : "68%",
              }}
              initial={{ opacity: 0, scale: 0.9, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -8 }}
              transition={{ duration: 0.3 }}
            >
              <p className="mb-1 text-xs font-black text-[var(--color-wolf-blue)]">{speech.label}</p>
              <p className="max-h-[80px] overflow-y-auto text-xs leading-relaxed text-[var(--color-wolf-muted)]">{speech.speech}</p>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
