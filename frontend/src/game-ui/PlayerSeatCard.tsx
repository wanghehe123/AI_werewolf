import { motion } from "framer-motion";
import type { PlayerVisualState } from "./gameVisualTypes";
import { avatarFor } from "./defaultAvatars";
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
  const roleKeyClass = role === "狼人" ? "role-werewolf" : role === "预言家" ? "role-seer" : role === "女巫" ? "role-witch" : role === "猎人" ? "role-hunter" : "";

  return (
    <motion.article
      className={`
        relative grid min-h-[86px] grid-cols-[36px_70px_1fr_28px] items-center gap-3 rounded-[22px] border px-3 py-2 transition-all
        ${!alive ? "border-[#d8dfef] bg-white/38 opacity-60 grayscale" : ""}
        ${alive && visualTone === "normal" ? "border-[var(--color-wolf-border)] bg-white/68" : ""}
        ${visualTone === "self" ? "border-[#8ba1ff] bg-[#eef3ff]" : ""}
        ${visualTone === "speaking" ? "border-[#8ba1ff] bg-white shadow-[0_16px_38px_rgba(91,118,255,0.2)]" : ""}
        ${visualTone === "selectable" ? "border-[#8ba1ff] bg-white/80 cursor-pointer hover:-translate-y-0.5 hover:shadow-[0_14px_30px_rgba(91,118,255,0.18)]" : ""}
        ${visualTone === "selected" ? "border-[var(--color-wolf-blue)] bg-[#edf2ff] cursor-pointer shadow-[0_16px_38px_rgba(91,118,255,0.22)]" : ""}
        ${isSheriffCandidate ? "border-[var(--color-wolf-amber)] bg-[#fff8e9]" : ""}
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

      <span className={`grid h-8 w-8 place-items-center rounded-full text-sm font-black text-white shadow-sm ${seat === 1 ? "bg-gradient-to-br from-[#f8c35a] to-[#e5a84d]" : "bg-[#9caad0]"}`}>
        {seat}
      </span>

      <div className="relative">
        <div className="h-16 w-16 overflow-hidden rounded-full bg-[#edf3ff] shadow-[0_10px_24px_rgba(95,119,176,0.2)]">
          <img src={avatarFor(avatarUrl, player.playerId || seat)} alt="" className="h-full w-full object-cover" />
        </div>

        {speaking && (
          <>
            <div className="absolute inset-0 rounded-full border-2 border-[var(--color-gold)] animate-[ripple-voice_1.5s_ease-out_infinite]" />
            <div className="absolute inset-0 rounded-full border-2 border-[var(--color-gold)] animate-[ripple-voice_1.5s_ease-out_0.5s_infinite]" />
          </>
        )}
      </div>

      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-2">
          <span className="text-sm font-bold text-[var(--color-wolf-muted)]">{seat}号</span>
          <strong className="truncate text-base leading-tight text-[#17213d]">{displayName}</strong>
          {role && <span className={`wolf-role-badge ${roleKeyClass}`}>{role}</span>}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-[var(--color-wolf-muted)]">
          <span className="wolf-online-dot" />
          <span>{alive ? "在线" : "离线"}</span>
          {isSelf && <span className="rounded-full bg-[#e8f0ff] px-2 py-0.5 text-xs font-bold text-[var(--color-wolf-blue)]">你</span>}
          {isSheriff && <span className="rounded-full bg-[#fff3d4] px-2 py-0.5 text-xs font-bold text-[#c88724]">警长</span>}
          {isSheriffCandidate && !isSheriff && <span className="rounded-full bg-[#fff3d4] px-2 py-0.5 text-xs font-bold text-[#c88724]">参选</span>}
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
        {!alive && (
          <span className="rounded-full bg-[#ffe5e5] px-2 py-0.5 text-xs font-bold text-[var(--color-wolf-red)] animate-[stamp-in_0.4s_ease-out]">
            出局
          </span>
        )}
        {voted && alive && <span className="rounded-full bg-[#e8f0ff] px-2 py-0.5 text-xs font-bold text-[var(--color-wolf-blue)]">已投</span>}
        {checkedCamp && (
          <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${checkedCamp === "good" ? "bg-[#ddfbea] text-[#17925a]" : "bg-[#ffe5e5] text-[var(--color-wolf-red)]"}`}>
            {checkedCamp === "good" ? "好人" : "狼人"}
          </span>
        )}
        {selected && <span className="rounded-full bg-[#e8f0ff] px-2 py-0.5 text-xs font-bold text-[var(--color-wolf-blue)]">目标</span>}
        </div>
      </div>

      <span aria-hidden="true" className="wolf-sound-bars justify-self-end">
        <i /><i /><i /><i />
      </span>
    </motion.article>
  );
}
