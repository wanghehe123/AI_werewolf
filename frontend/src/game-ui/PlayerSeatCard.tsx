import { motion } from "framer-motion";
import type { PlayerVisualState } from "./gameVisualTypes";
import handRaiseIcon from "../icon/举手.png";

interface PlayerSeatCardProps {
  player: PlayerVisualState;
  onClick?: () => void;
}

export function PlayerSeatCard({ player, onClick }: PlayerSeatCardProps) {
  const {
    seat,
    displayName,
    avatarUrl,
    alive,
    isSelf,
    isSheriff,
    isSheriffCandidate,
    speaking,
    voted,
    selectable,
    selected,
    checkedCamp,
    roleLabel: role,
    visualTone,
  } = player;

  const isInteractive = selectable && alive;

  return (
    <motion.article
      className={`
        relative flex flex-col items-center gap-1 p-3 rounded-xl border transition-all
        ${!alive ? "border-[var(--color-dead-ink)] bg-[var(--color-dead-ink)]/40 opacity-60" : ""}
        ${alive && visualTone === "normal" ? "border-[var(--color-warm-border)] bg-[var(--color-warm-card)]" : ""}
        ${visualTone === "self" ? "border-[var(--color-green-seer)]/40 bg-[var(--color-green-bg)]/20" : ""}
        ${visualTone === "speaking" ? "border-[var(--color-gold)] bg-[var(--color-warm-card)]" : ""}
        ${visualTone === "selectable" ? "border-[var(--color-blue-night)]/50 bg-[var(--color-warm-card)] cursor-pointer hover:border-[var(--color-blue-night)]" : ""}
        ${visualTone === "selected" ? "border-[var(--color-gold)] bg-[var(--color-gold)]/10 cursor-pointer" : ""}
        ${isSheriffCandidate ? "border-[var(--color-amber)] bg-[var(--color-amber-bg)]/20" : ""}
        ${isInteractive ? "cursor-pointer" : ""}
      `}
      onClick={isInteractive ? onClick : undefined}
      whileHover={isInteractive ? { scale: 1.04 } : {}}
      whileTap={isInteractive ? { scale: 0.97 } : {}}
      animate={{
        boxShadow: speaking
          ? ["0 0 0 0 rgba(215,167,86,0.4)", "0 0 20px 4px rgba(215,167,86,0.6)", "0 0 0 0 rgba(215,167,86,0.4)"]
          : isSheriffCandidate
            ? ["0 0 0 0 rgba(215,167,86,0.2)", "0 0 8px 2px rgba(215,167,86,0.4)", "0 0 0 0 rgba(215,167,86,0.2)"]
            : "0 0 0px rgba(215,167,86,0)",
      }}
      transition={{
        boxShadow: (speaking || isSheriffCandidate) ? { duration: 2, repeat: Infinity } : { duration: 0.3 },
      }}
      role={isInteractive ? "button" : undefined}
      aria-label={isInteractive ? `选择 ${seat}号 ${displayName} 为目标` : `${seat}号 ${displayName}`}
      tabIndex={isInteractive ? 0 : undefined}
    >
      {/* Sheriff candidate hand-raise indicator */}
      {isSheriffCandidate && (
        <motion.div
          className="absolute -top-2 -right-2 z-10"
          initial={{ scale: 0, rotate: -20 }}
          animate={{ scale: [1, 1.15, 1], rotate: [0, 5, -5, 0] }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          <img src={handRaiseIcon} alt="举手参选" className="w-8 h-8 drop-shadow-md" />
        </motion.div>
      )}

      {/* Avatar */}
      <div className="relative">
        <div className="w-10 h-10 rounded-full bg-[var(--color-warm-border)] flex items-center justify-center text-sm font-bold text-[var(--color-text-dim)] overflow-hidden">
          {avatarUrl ? <img src={avatarUrl} alt="" className="w-full h-full object-cover" /> : displayName.slice(0, 1)}
        </div>

        {/* Speaking ripple */}
        {speaking && (
          <>
            <div className="absolute inset-0 rounded-full border-2 border-[var(--color-gold)] animate-[ripple-voice_1.5s_ease-out_infinite]" />
            <div className="absolute inset-0 rounded-full border-2 border-[var(--color-gold)] animate-[ripple-voice_1.5s_ease-out_0.5s_infinite]" />
          </>
        )}
      </div>

      {/* Name & seat */}
      <div className="text-center">
        <div className="flex items-center gap-1 justify-center">
          <span className="text-xs text-[var(--color-text-muted)]">{seat}号</span>
          <strong className="text-sm leading-tight">{displayName}</strong>
        </div>
      </div>

      {/* Status badges */}
      <div className="flex flex-wrap gap-0.5 justify-center">
        {isSelf && <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-green-bg)] text-[var(--color-green-seer)]">你</span>}
        {isSheriff && <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-amber-bg)] text-[var(--color-amber)]">警长</span>}
        {isSheriffCandidate && !isSheriff && <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-amber-bg)]/60 text-[var(--color-amber)]">参选</span>}
        {role && <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-warm-border)]">{role}</span>}
        {!alive && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-red-bg)] text-red-400 animate-[stamp-in_0.4s_ease-out]">
            出局
          </span>
        )}
        {voted && alive && <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-blue-bg)] text-[var(--color-blue-night)]">已投</span>}
        {checkedCamp && (
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${checkedCamp === "good" ? "bg-[var(--color-green-bg)] text-[var(--color-green-seer)]" : "bg-[var(--color-red-bg)] text-red-400"}`}>
            {checkedCamp === "good" ? "好人" : "狼人"}
          </span>
        )}
        {selected && <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-gold)]/20 text-[var(--color-gold)]">目标</span>}
      </div>
    </motion.article>
  );
}
