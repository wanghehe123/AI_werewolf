import type { AdminGameDto } from "../types";

interface AdminGamesPageProps {
  games: AdminGameDto[];
  onRefresh: () => void;
}

export function AdminGamesPage({ games, onRefresh }: AdminGamesPageProps) {
  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="scene-kicker">GAMES</p>
          <h2>游戏记录</h2>
        </div>
        <button className="ghost-action" type="button" onClick={onRefresh}>
          刷新
        </button>
      </header>
      <table className="admin-table">
        <thead>
          <tr>
            <th>游戏</th>
            <th>板子</th>
            <th>阶段</th>
            <th>天数</th>
            <th>胜方</th>
          </tr>
        </thead>
        <tbody>
          {games.map((game) => (
            <tr key={game.game_id}>
              <td>{game.game_id}</td>
              <td>{game.board_id}</td>
              <td>{game.phase}</td>
              <td>{game.day_count}</td>
              <td>{game.winner ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {games.length === 0 ? <p className="admin-empty">暂无游戏记录</p> : null}
    </section>
  );
}
