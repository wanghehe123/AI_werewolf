import { GameTableShell } from "./game-ui/GameTableShell";
import type { GameStateDto, SeerCheckResult, StreamingSpeechDto, SubmitActionInput } from "./types";

interface GameTableProps {
  game: GameStateDto;
  onSubmitAction: (action: SubmitActionInput) => Promise<void>;
  pending: boolean;
  streamingSpeeches?: Record<string, StreamingSpeechDto>;
  seerResults?: Record<string, SeerCheckResult>;
}

export function GameTable({ game, onSubmitAction, pending, streamingSpeeches = {}, seerResults = {} }: GameTableProps) {
  return (
    <GameTableShell
      game={game}
      onSubmitAction={onSubmitAction}
      pending={pending}
      streamingSpeeches={streamingSpeeches}
      seerResults={seerResults}
    />
  );
}
