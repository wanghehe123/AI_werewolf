import { useMemo } from "react";
import { motion } from "framer-motion";
import { PlayerSeatCard } from "./PlayerSeatCard";
import type { PlayerVisualState } from "./gameVisualTypes";

interface PlayerRingProps {
  players: PlayerVisualState[];
  onSelectTarget?: (playerId: string) => void;
}

/**
 * Positions players around a central table area.
 * For 6-8 players, uses a CSS grid layout that creates an oval arrangement.
 */
export function PlayerRing({ players, onSelectTarget }: PlayerRingProps) {
  const count = players.length;

  // Generate grid positions for up to 8 players around a center
  // Layout: top row, left-right sides, bottom row
  const positions = useMemo(() => {
    if (count <= 4) {
      return [
        { row: "1", col: "1" }, // top-left
        { row: "1", col: "3" }, // top-right
        { row: "3", col: "3" }, // bottom-right
        { row: "3", col: "1" }, // bottom-left
      ];
    }
    // 6+ players: 3-2-center-2-3 arrangement
    return [
      { row: "1", col: "1" }, // top-left
      { row: "1", col: "2" }, // top-center
      { row: "1", col: "3" }, // top-right
      { row: "2", col: "3" }, // mid-right
      { row: "3", col: "3" }, // bottom-right
      { row: "3", col: "2" }, // bottom-center
      { row: "3", col: "1" }, // bottom-left
      { row: "2", col: "1" }, // mid-left
    ];
  }, [count]);

  return (
    <div
      className="grid gap-2 p-2"
      style={{
        gridTemplateColumns: "1fr 1fr 1fr",
        gridTemplateRows: "auto 1fr auto",
      }}
    >
      {/* Center slot spanning the middle row */}
      <div style={{ gridRow: "2", gridColumn: "1 / 4" }} className="flex items-center justify-center">
        {/* TableCenter is rendered by GameTableShell here */}
        <div id="table-center-slot" />
      </div>

      {players.map((player, index) => {
        const pos = positions[index] ?? { row: "1", col: "1" };
        return (
          <motion.div
            key={player.playerId}
            style={{ gridRow: pos.row, gridColumn: pos.col }}
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.06, duration: 0.3, type: "spring", stiffness: 180 }}
          >
            <PlayerSeatCard
              player={player}
              onClick={() => onSelectTarget?.(player.playerId)}
            />
          </motion.div>
        );
      })}
    </div>
  );
}
