import { PhaseSceneRouter } from "./PhaseSceneRouter";
import type { GameStateDto, SubmitActionInput } from "./types";

interface GameTableProps {
  game: GameStateDto;
  onSubmitAction: (action: SubmitActionInput) => Promise<void>;
  pending: boolean;
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

export function GameTable({ game, onSubmitAction, pending }: GameTableProps) {
  return (
    <main className="game-table">
      <header className="phase-banner">
        <div>
          <p className="scene-kicker">AI WEREWOLF ROOM</p>
          <h1>{phaseLabels[game.phase]}</h1>
        </div>
        <div className="phase-meta">
          <span>第 {game.day_count} 天</span>
          <span>{game.winner ? `胜利：${game.winner}` : "对局进行中"}</span>
        </div>
      </header>

      <section className="table-layout">
        <div className="seat-ring" aria-label="玩家座位">
          {game.players.map((player) => (
            <article className={`player-seat ${player.alive ? "" : "is-dead"} ${player.speaking ? "is-speaking" : ""}`} key={player.player_id}>
              <div className="avatar" aria-hidden="true">
                {player.avatar_url ? <img src={player.avatar_url} alt="" /> : player.display_name.slice(0, 1)}
              </div>
              <div>
                <strong>{player.display_name}</strong>
                <p>{player.seat}号位</p>
              </div>
              <div className="seat-tags">
                {player.role_key && <span>{roleLabel(player.role_key)}</span>}
                {player.sheriff && <span>警长</span>}
                {!player.alive && <span>出局</span>}
                {player.voted && <span>已投票</span>}
              </div>
            </article>
          ))}
        </div>

        <aside className="event-log" aria-label="事件时间线">
          <div className="panel-title">事件时间线</div>
          {game.public_events.length === 0 ? (
            <p className="empty-state">等待第一条事件。</p>
          ) : (
            game.public_events.map((event, index) => (
              <p key={`${event.event_type}-${index}`}>
                <span>{event.event_type}</span>
                {event.payload.message}
              </p>
            ))
          )}
        </aside>
      </section>

      <PhaseSceneRouter game={game} onSubmitAction={onSubmitAction} pending={pending} />
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
