import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { PhaseStatusBar } from "./PhaseStatusBar";
import { TableCenter } from "./TableCenter";
import { EventRail } from "./EventRail";
import { ActionDock } from "./ActionDock";
import { SpeechBubbleLayer } from "./SpeechBubbleLayer";
import { EffectsLayer } from "./EffectsLayer";
import { PlayerSeatCard } from "./PlayerSeatCard";
import { derivePlayerVisualStates, eventMessage, roleLabel } from "./gameVisuals";
import type { GameStateDto, SeerCheckResult, StreamingSpeechDto, SubmitActionInput } from "../types";
import type { PlayerVisualState } from "./gameVisualTypes";

interface GameTableShellProps {
  game: GameStateDto;
  onSubmitAction: (action: SubmitActionInput) => Promise<void>;
  pending: boolean;
  streamingSpeeches?: Record<string, StreamingSpeechDto>;
  seerResults?: Record<string, SeerCheckResult>;
}

/**
 * For 6 players, arrange as:
 *   [seat1] [seat2] [seat3]
 *   [seat6] [ TABLE ] [seat4]
 *          [seat5]
 * For 8 players:
 *   [seat1] [seat2] [seat3]
 *   [seat8] [ TABLE ] [seat4]
 *   [seat7] [seat6] [seat5]
 */
function getSeatLayout(players: PlayerVisualState[]) {
  const n = players.length;
  if (n <= 4) {
    const top = players.slice(0, 2);
    const bottom = players.slice(2);
    return { top, middleLeft: [], middleRight: [], bottom, bottomExtra: [] };
  }
  if (n <= 6) {
    return {
      top: [players[0], players[1], players[2]],
      middleLeft: [players[5]],
      middleRight: [players[3]],
      bottom: [players[4]],
      bottomExtra: [],
    };
  }
  // 7+ players: top=3, middle=2, rest in bottom row(s)
  const bottomAll = players.slice(4, n - 1);
  return {
    top: [players[0], players[1], players[2]],
    middleLeft: [players[n - 1]],
    middleRight: [players[3]],
    bottom: bottomAll.slice(0, 3),
    bottomExtra: bottomAll.slice(3),
  };
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
  const layout = getSeatLayout(playerStates);

  return (
    <main className="flex flex-col gap-4 max-w-7xl mx-auto px-4 py-4 relative h-screen overflow-hidden">
      <PhaseStatusBar game={game} />

      <section
        aria-label="游戏桌面区域"
        className="grid grid-cols-[minmax(0,1fr)_260px] gap-4 flex-1 min-h-0 overflow-hidden"
      >
        <div className="relative min-h-0 overflow-y-auto pr-1 pb-1">
          {/* Table layout with players around center */}
          <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] gap-2 content-start min-h-full">
            {/* Top row */}
            {layout.top.map((player) => (
              <SeatWrapper key={player.playerId}>
                <PlayerSeatCard player={player} onClick={() => handleSelectTarget(player.playerId)} />
              </SeatWrapper>
            ))}
            {/* Fill top row to 3 cols */}
            {layout.top.length < 3 && Array.from({ length: 3 - layout.top.length }).map((_, i) => (
              <div key={`top-fill-${i}`} />
            ))}

            {/* Middle row: left | center | right */}
            {layout.middleLeft.map((player) => (
              <SeatWrapper key={player.playerId}>
                <PlayerSeatCard player={player} onClick={() => handleSelectTarget(player.playerId)} />
              </SeatWrapper>
            ))}
            {layout.middleLeft.length === 0 && <div />}

            <TableCenter game={game} latestEventMessage={latestEventMessage} />

            {layout.middleRight.map((player) => (
              <SeatWrapper key={player.playerId}>
                <PlayerSeatCard player={player} onClick={() => handleSelectTarget(player.playerId)} />
              </SeatWrapper>
            ))}
            {layout.middleRight.length === 0 && <div />}

            {/* Bottom row */}
            {layout.bottom.map((player) => (
              <SeatWrapper key={player.playerId}>
                <PlayerSeatCard player={player} onClick={() => handleSelectTarget(player.playerId)} />
              </SeatWrapper>
            ))}
            {/* Fill empty slots in bottom row */}
            {layout.bottom.length === 1 && <div />}
            {layout.bottom.length === 2 && <div />}

            {/* Extra bottom row for 9+ players */}
            {layout.bottomExtra.map((player) => (
              <SeatWrapper key={player.playerId}>
                <PlayerSeatCard player={player} onClick={() => handleSelectTarget(player.playerId)} />
              </SeatWrapper>
            ))}
            {/* Fill empty slots in extra bottom row */}
            {layout.bottomExtra.length === 1 && <><div /><div /></>}
            {layout.bottomExtra.length === 2 && <div />}
          </div>

          <SpeechBubbleLayer players={playerStates} streamingSpeeches={streamingSpeeches} />
        </div>

        <EventRail events={game.public_events} streamingSpeeches={streamingEntries} />
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
        <div className="fixed inset-0 bg-black/50 z-40 flex items-center justify-center overflow-y-auto p-4">
          <GameOverReview game={game} />
        </div>
      )}
    </main>
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
    <section className="p-6 rounded-xl border border-[var(--color-gold)]/30 bg-[var(--color-warm-card)]">
      <h2 className="text-lg font-bold mb-4">身份揭晓</h2>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {game.players.map((player, index) => (
          <motion.div
            key={player.player_id}
            className={`p-3 rounded-lg border text-center ${
              player.role_key === "werewolf"
                ? "border-red-800/40 bg-[var(--color-red-bg)]/30"
                : "border-[var(--color-warm-border)] bg-[var(--color-warm-bg)]"
            }`}
            initial={{ rotateY: 90, opacity: 0 }}
            animate={{ rotateY: 0, opacity: 1 }}
            transition={{ delay: index * 0.15, duration: 0.4 }}
          >
            <p className="text-sm font-semibold">{player.seat}号 {player.display_name}</p>
            <p className="text-xs text-[var(--color-text-dim)]">
              {roleLabel(player.role_key ?? "unknown")}
            </p>
            {player.sheriff && <p className="text-xs text-[var(--color-amber)] mt-1">警长</p>}
          </motion.div>
        ))}
      </div>
      <a
        className="mt-4 px-5 py-2.5 rounded-lg bg-[var(--color-gold)] text-[var(--color-warm-bg)] font-semibold hover:bg-[var(--color-gold-dim)] no-underline text-center inline-block text-sm"
        href="/"
      >
        返回大厅
      </a>
    </section>
  );
}
