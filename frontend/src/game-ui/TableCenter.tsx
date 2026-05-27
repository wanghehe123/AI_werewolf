import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { buildVisualEvents, phaseLabel } from "./gameVisuals";
import { VoteTally } from "./VoteTally";
import type { GameStateDto } from "../types";

interface TableCenterProps {
  game: GameStateDto;
  latestEventMessage?: string;
  streamingSpeeches?: Array<{ label: string; speech: string }>;
}

export function TableCenter({ game, latestEventMessage, streamingSpeeches = [] }: TableCenterProps) {
  const [activeTab, setActiveTab] = useState<"speech" | "event">("speech");
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
  const visualEvents = useMemo(() => buildVisualEvents(game.public_events), [game.public_events]);
  const speechEvents = visualEvents.filter((event) => event.filter === "speech");
  const eventItems = activeTab === "speech" ? speechEvents : visualEvents;
  const displayedItems = (eventItems.length > 0 ? eventItems : visualEvents).slice(-8);

  return (
    <div className="wolf-glass relative grid h-full min-h-0 grid-rows-[auto_1fr] overflow-hidden rounded-[32px]">
      <div className="flex items-center justify-center border-b border-[var(--color-wolf-line)]">
        <button
          role="tab"
          aria-selected={activeTab === "speech"}
          className={`min-w-[180px] border-b-2 px-8 py-5 text-base font-black transition ${
            activeTab === "speech"
              ? "border-[var(--color-wolf-blue)] text-[var(--color-wolf-blue)]"
              : "border-transparent text-[var(--color-wolf-muted)]"
          }`}
          onClick={() => setActiveTab("speech")}
        >
          发言
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "event"}
          className={`min-w-[180px] border-b-2 px-8 py-5 text-base font-black transition ${
            activeTab === "event"
              ? "border-[var(--color-wolf-blue)] text-[var(--color-wolf-blue)]"
              : "border-transparent text-[var(--color-wolf-muted)]"
          }`}
          onClick={() => setActiveTab("event")}
        >
          事件
        </button>
      </div>

      <div className="grid min-h-0 grid-rows-[auto_1fr] gap-5 p-7">
        <section className="rounded-[26px] bg-white/58 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.72)]">
          <div className="flex items-start gap-4">
            <span className="grid h-14 w-14 shrink-0 place-items-center rounded-full bg-[#fff8da] text-3xl shadow-sm">{isNight ? "🌙" : "☀"}</span>
            <div className="min-w-0">
              <motion.h2
                className="text-2xl font-black text-[#17213d]"
                key={game.phase}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
              >
                第 {game.day_count} 天 · {centerText}
              </motion.h2>
              <p className="mt-2 text-base text-[var(--color-wolf-muted)]">
                {isNight ? "夜色降临，请根据你的身份完成夜晚行动。" : latestEventMessage || "昨夜平安夜，无人死亡。"}
              </p>
            </div>
          </div>

          {speakingPlayer && (
            <motion.div
              className="mt-4 flex items-center gap-2 rounded-full bg-[#edf3ff] px-4 py-2 text-sm font-bold text-[var(--color-wolf-blue)]"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              key={speakingPlayer.player_id}
            >
              <span className="h-2 w-2 rounded-full bg-[var(--color-wolf-blue)] animate-[breathing_1.5s_ease-in-out_infinite]" />
              正在发言：{speakingPlayer.seat}号 {speakingPlayer.display_name}
            </motion.div>
          )}
        </section>

        <section
          aria-label="当前事件摘要"
          className="min-h-0 overflow-y-auto rounded-[26px] bg-white/54 p-5 [scrollbar-gutter:stable]"
        >
          <div className="grid gap-1">
            {displayedItems.map((event, index) => (
              <motion.article
                key={event.id}
                className="grid grid-cols-[46px_1fr_auto] gap-4 border-b border-[var(--color-wolf-line)] py-4 last:border-b-0"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.02 }}
              >
                <span className="grid h-11 w-11 place-items-center rounded-full bg-[#edf3ff] text-xl">{event.filter === "speech" ? "💬" : "📜"}</span>
                <span className="min-w-0">
                  <strong className="block text-[#1f2b4c]">{event.label}</strong>
                  <span className="mt-1 block text-sm leading-6 text-[var(--color-wolf-muted)]">{event.message}</span>
                </span>
                <span className="text-sm text-[var(--color-wolf-soft)]">{String(10 + index).padStart(2, "0")}:0{index}</span>
              </motion.article>
            ))}

            {displayedItems.length === 0 && (
              <p className="py-10 text-center text-[var(--color-wolf-muted)]">
                {activeTab === "speech" ? "等待第一位玩家发言。" : "等待第一条事件。"}
              </p>
            )}

            {streamingSpeeches.map((speech, index) => (
              <motion.article
                className="rounded-[18px] bg-[#edf3ff] p-4 text-sm text-[var(--color-wolf-blue)]"
                key={`streaming-${index}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <span className="mr-2 font-black">实时发言</span>
                <span className="font-bold">{speech.label}：</span>
                <span className="text-[#64749d]">{speech.speech}</span>
              </motion.article>
            ))}
          </div>

          <VoteTally game={game} />
        </section>
      </div>

      {isGameOver && game.winner && (
        <motion.div
          className={`absolute bottom-7 left-1/2 -translate-x-1/2 rounded-[22px] border px-6 py-3 text-center ${
            game.winner === "wolves"
              ? "border-[#ffd1d1] bg-[#fff0f0] text-[#b8313d]"
              : "border-[#c9f5dc] bg-[#ecfff4] text-[#168552]"
          }`}
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 200 }}
        >
          <p className="text-lg font-black">
            {game.winner === "wolves" ? "狼人阵营" : "好人阵营"} 获得胜利
          </p>
        </motion.div>
      )}

      {isNight && (
        <div className="pointer-events-none absolute inset-0 rounded-[32px] bg-gradient-to-b from-[#6f83ff]/5 to-transparent" />
      )}
    </div>
  );
}
