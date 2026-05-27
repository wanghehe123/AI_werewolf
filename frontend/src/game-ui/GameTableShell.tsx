import { useState, useEffect, useCallback } from "react";
import type React from "react";
import { motion } from "framer-motion";
import { PhaseStatusBar } from "./PhaseStatusBar";
import { TableCenter } from "./TableCenter";
import { ActionDock } from "./ActionDock";
import { SpeechBubbleLayer } from "./SpeechBubbleLayer";
import { EffectsLayer } from "./EffectsLayer";
import { PlayerSeatCard } from "./PlayerSeatCard";
import { derivePlayerVisualStates, eventMessage, roleLabel } from "./gameVisuals";
import { emptySeatAvatar } from "./defaultAvatars";
import type { GameStateDto, SeerCheckResult, StreamingSpeechDto, SubmitActionInput } from "../types";
import type { PlayerVisualState } from "./gameVisualTypes";

interface GameTableShellProps {
  game: GameStateDto;
  onSubmitAction: (action: SubmitActionInput) => Promise<void>;
  pending: boolean;
  streamingSpeeches?: Record<string, StreamingSpeechDto>;
  seerResults?: Record<string, SeerCheckResult>;
}

export function GameTableShell({
  game,
  onSubmitAction,
  pending,
  streamingSpeeches = {},
  seerResults = {},
}: GameTableShellProps) {
  const [selectedTargetId, setSelectedTargetId] = useState<string | null>(null);
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

  useEffect(() => {
    setSelectedTargetId(null);
  }, [game.phase]);

  const handleSelectTarget = useCallback((playerId: string | null) => {
    setSelectedTargetId(playerId);
  }, []);

  const playerStates = derivePlayerVisualStates(game, selectedTargetId, seerResults);
  const latestEventMessage = game.public_events.length > 0
    ? eventMessage(game.public_events[game.public_events.length - 1])
    : undefined;

  const streamingEntries = Object.entries(streamingSpeeches)
    .filter(([, v]) => v.speech.trim().length > 0)
    .map(([, v]) => v);

  const isGameOver = game.phase === "game_over";
  const seatsByNumber = new Map(playerStates.map((player) => [player.seat, player]));
  const leftSeats = [1, 2, 3, 4, 5, 6];
  const rightSeats = [7, 8, 9, 10, 11, 12];

  return (
    <main className="wolf-page h-screen overflow-hidden">
      <div className="wolf-content mx-auto grid h-full max-w-[1540px] grid-rows-[auto_1fr_auto] gap-4 px-8 py-6">
        <PhaseStatusBar game={game} />

        <section
          aria-label="游戏桌面区域"
          className="grid min-h-0 grid-cols-[364px_minmax(420px,1fr)_364px] gap-6 overflow-hidden"
        >
          <SeatColumn
            seats={leftSeats}
            seatsByNumber={seatsByNumber}
            onSelectTarget={handleSelectTarget}
          />

          <div className="relative min-h-0">
            <TableCenter
              game={game}
              latestEventMessage={latestEventMessage}
              streamingSpeeches={streamingEntries}
            />
            <SpeechBubbleLayer players={playerStates} streamingSpeeches={streamingSpeeches} />
          </div>

          <SeatColumn
            seats={rightSeats}
            seatsByNumber={seatsByNumber}
            onSelectTarget={handleSelectTarget}
          />
        </section>

        <ActionDock
          game={game}
          onSubmitAction={onSubmitAction}
          pending={pending}
          selectedTargetId={selectedTargetId}
          onSelectTarget={handleSelectTarget}
        />

        <EffectsLayer
          game={game}
          seerOverlay={overlayResult}
          onDismissOverlay={() => setOverlayResult(null)}
        />

        {isGameOver && (
          <div className="fixed inset-0 z-40 flex items-center justify-center overflow-y-auto bg-[#173057]/30 p-4 backdrop-blur-sm">
            <GameOverReview game={game} />
          </div>
        )}
      </div>
    </main>
  );
}

function SeatColumn({
  seats,
  seatsByNumber,
  onSelectTarget,
}: {
  seats: number[];
  seatsByNumber: Map<number, PlayerVisualState>;
  onSelectTarget: (playerId: string | null) => void;
}) {
  return (
    <div className="grid min-h-0 content-start gap-4 overflow-y-auto overflow-x-hidden pr-1">
      {seats.map((seat) => {
        const player = seatsByNumber.get(seat);
        return player ? (
          <SeatWrapper key={player.playerId}>
            <PlayerSeatCard player={player} onClick={() => onSelectTarget(player.playerId)} />
          </SeatWrapper>
        ) : (
          <EmptySeatCard key={`empty-${seat}`} seat={seat} />
        );
      })}
    </div>
  );
}

function EmptySeatCard({ seat }: { seat: number }) {
  return (
    <article className="grid min-h-[86px] grid-cols-[36px_70px_1fr] items-center gap-3 rounded-[22px] border border-[#dfe7f8] bg-white/42 px-3 py-2 opacity-70">
      <span className="grid h-8 w-8 place-items-center rounded-full bg-[#c5d0ea] text-sm font-black text-white">{seat}</span>
      <img className="h-16 w-16 rounded-full opacity-70" src={emptySeatAvatar()} alt="" />
      <div>
        <span className="text-sm font-bold text-[#b1bdd8]">{seat}号</span>
        <p className="mt-1 font-bold text-[#b1bdd8]">空位</p>
      </div>
    </article>
  );
}

function SeatWrapper({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, type: "spring", stiffness: 180 }}
    >
      {children}
    </motion.div>
  );
}

function GameOverReview({ game }: { game: GameStateDto }) {
  return (
    <section className="wolf-glass rounded-[28px] p-6 text-[#17213d]">
      <h2 className="mb-4 text-lg font-black">身份揭晓</h2>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {game.players.map((player, index) => (
          <motion.div
            key={player.player_id}
            className={`rounded-[18px] border p-3 text-center ${
              player.role_key === "werewolf"
                ? "border-[#ffd1d1] bg-[#fff0f0]"
                : "border-[#dfe7f8] bg-white/62"
            }`}
            initial={{ rotateY: 90, opacity: 0 }}
            animate={{ rotateY: 0, opacity: 1 }}
            transition={{ delay: index * 0.15, duration: 0.4 }}
          >
            <p className="text-sm font-semibold">{player.seat}号 {player.display_name}</p>
            <p className="text-xs text-[var(--color-wolf-muted)]">
              {roleLabel(player.role_key ?? "unknown")}
            </p>
            {player.sheriff && <p className="mt-1 text-xs text-[#c88724]">警长</p>}
          </motion.div>
        ))}
      </div>
      <a
        className="wolf-primary mt-4 inline-block rounded-[18px] px-5 py-2.5 text-center text-sm font-bold no-underline"
        href="/"
      >
        返回大厅
      </a>
    </section>
  );
}
