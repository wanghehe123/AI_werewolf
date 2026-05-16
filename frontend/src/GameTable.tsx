import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { PhaseSceneRouter } from "./PhaseSceneRouter";
import type { GameStateDto, SeerCheckResult, StreamingSpeechDto, SubmitActionInput } from "./types";

interface GameTableProps {
  game: GameStateDto;
  onSubmitAction: (action: SubmitActionInput) => Promise<void>;
  pending: boolean;
  streamingSpeeches?: Record<string, StreamingSpeechDto>;
  seerResults?: Record<string, SeerCheckResult>;
}

const phaseLabels: Record<GameStateDto["phase"], string> = {
  setup: "准备开局",
  night: "夜晚行动",
  day_announcement: "昨夜信息",
  sheriff_election: "警长竞选",
  sheriff_speech: "竞选发言",
  day_speech: "白天发言",
  exile_vote: "放逐投票",
  last_words: "遗言",
  game_over: "游戏复盘"
};

export function GameTable({ game, onSubmitAction, pending, streamingSpeeches = {}, seerResults = {} }: GameTableProps) {
  const streamingSpeechEntries = Object.entries(streamingSpeeches).filter(([, value]) => value.speech.trim().length > 0);

  const [overlayResult, setOverlayResult] = useState<SeerCheckResult | null>(null);
  const [prevResultCount, setPrevResultCount] = useState(0);
  const resultKeys = Object.keys(seerResults);

  useEffect(() => {
    if (resultKeys.length > prevResultCount) {
      setPrevResultCount(resultKeys.length);
      const latestKey = resultKeys[resultKeys.length - 1];
      setOverlayResult(seerResults[latestKey]);
      const timer = setTimeout(() => setOverlayResult(null), 3500);
      return () => clearTimeout(timer);
    }
  }, [resultKeys.length]);

  return (
    <main className="flex flex-col gap-6 max-w-7xl mx-auto px-4 py-6">
      <motion.header
        className="flex justify-between items-center p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]"
        key={`${game.phase}-${game.day_count}`}
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, type: "spring", stiffness: 150 }}
      >
        <div>
          <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-1">AI WEREWOLF ROOM</p>
          <h1 className="text-2xl font-bold">{phaseLabels[game.phase]}</h1>
        </div>
        <div className="flex gap-4 text-sm text-[var(--color-text-dim)]">
          <span>第 {game.day_count} 天</span>
          <span>{game.winner ? `胜利：${game.winner}` : "对局进行中"}</span>
        </div>
      </motion.header>

      <section className="grid grid-cols-[1fr_280px] gap-6 max-md:grid-cols-1">
        <div className="grid grid-cols-3 gap-3" aria-label="玩家座位">
          {game.players.map((player, index) => (
            <motion.article
              className={`flex flex-col items-center gap-2 p-4 rounded-xl border transition-all
                ${player.alive ? "border-[var(--color-warm-border)] bg-[var(--color-warm-card)]" : "border-[var(--color-warm-border)] bg-[var(--color-warm-card)] opacity-50"}
                ${player.speaking ? "!border-[var(--color-gold)]" : ""}
              `}
              key={player.player_id}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{
                opacity: 1,
                scale: 1,
                boxShadow: player.speaking
                  ? "0 0 24px rgba(215, 167, 86, 0.6)"
                  : "0 0 0px rgba(215, 167, 86, 0)"
              }}
              transition={{
                opacity: { delay: index * 0.08, duration: 0.3 },
                scale: { delay: index * 0.08, duration: 0.3, type: "spring", stiffness: 200 },
                boxShadow: { duration: 0.4 }
              }}
            >
              <div className="w-12 h-12 rounded-full bg-[var(--color-warm-border)] flex items-center justify-center text-lg font-bold text-[var(--color-text-dim)] overflow-hidden" aria-hidden="true">
                {player.avatar_url ? <img src={player.avatar_url} alt="" /> : player.display_name.slice(0, 1)}
              </div>
              <div>
                <strong>{player.display_name}</strong>
                <p>{player.seat}号位</p>
              </div>
              <div className="flex flex-wrap gap-1 justify-center">
                {player.role_key && <span className="text-xs px-2 py-0.5 rounded bg-[var(--color-warm-border)]">{roleLabel(player.role_key)}</span>}
                {player.sheriff && <span className="text-xs px-2 py-0.5 rounded bg-[var(--color-amber-bg)] text-[var(--color-amber)]">警长</span>}
                {!player.alive && <span className="text-xs px-2 py-0.5 rounded bg-[var(--color-red-bg)] text-red-400">出局</span>}
                {player.voted && <span className="text-xs px-2 py-0.5 rounded bg-[var(--color-blue-bg)] text-[var(--color-blue-night)]">已投票</span>}
                {seerResults[player.player_id] && (
                  <span className={`text-xs px-2 py-0.5 rounded ${seerResults[player.player_id].camp === "good" ? "bg-[var(--color-green-bg)] text-[var(--color-green-seer)]" : "bg-[var(--color-red-bg)] text-red-400"}`}>
                    {seerResults[player.player_id].camp === "good" ? "好" : "狼"}
                  </span>
                )}
              </div>
            </motion.article>
          ))}
        </div>

        <aside className="flex flex-col gap-2 p-4 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)] max-h-[calc(100vh-220px)] overflow-y-auto" aria-label="事件时间线">
          <div className="text-sm font-semibold text-[var(--color-text-dim)] pb-2 border-b border-[var(--color-warm-border)]">事件时间线</div>
          {game.public_events.length === 0 ? (
            <motion.p
              className="text-sm text-[var(--color-text-muted)] italic"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              等待第一条事件。
            </motion.p>
          ) : (
            game.public_events.map((event, index) => (
              <motion.p
                key={`${event.event_type}-${index}`}
                className="text-sm"
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: Math.min(index * 0.03, 0.5), duration: 0.25 }}
              >
                <span className="text-xs text-[var(--color-text-muted)] mr-2">{event.event_type}</span>
                {event.payload.message}
              </motion.p>
            ))
          )}
          <AnimatePresence>
            {streamingSpeechEntries.map(([playerId, value]) => (
              <motion.p
                className="text-sm text-[var(--color-gold)]"
                key={`streaming-${playerId}`}
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
              >
                <span className="text-xs text-[var(--color-text-muted)] mr-2">speech_delta</span>
                {value.label}：{value.speech}
              </motion.p>
            ))}
          </AnimatePresence>
        </aside>
      </section>

      <PhaseSceneRouter game={game} onSubmitAction={onSubmitAction} pending={pending} />

      <AnimatePresence>
        {overlayResult && (
          <motion.div
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            onClick={() => setOverlayResult(null)}
          >
            <motion.div
              className={`p-8 rounded-2xl text-center min-w-[280px] backdrop-blur ${
                overlayResult.camp === "good"
                  ? "bg-[var(--color-green-bg)]/90 border-2 border-[var(--color-green-seer)]"
                  : "bg-[var(--color-red-bg)]/90 border-2 border-red-400"
              }`}
              initial={{ scale: 0.5, opacity: 0, y: 30 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.8, opacity: 0, y: -20 }}
              transition={{ type: "spring", stiffness: 300, damping: 20 }}
            >
              <p className="text-sm text-[var(--color-text-dim)] mb-2">查验结果</p>
              <h2 className="text-2xl font-bold mb-2">{overlayResult.targetLabel}</h2>
              <p className={`text-lg font-semibold ${overlayResult.camp === "good" ? "text-[var(--color-green-seer)]" : "text-red-400"}`}>
                {overlayResult.camp === "good" ? "好人阵营" : "狼人阵营"}
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}

function roleLabel(roleKey: string): string {
  const labels: Record<string, string> = {
    werewolf: "狼人",
    seer: "预言家",
    witch: "女巫",
    hunter: "猎人",
    villager: "村民"
  };
  return labels[roleKey] ?? roleKey;
}
