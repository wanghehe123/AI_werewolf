interface DashboardStats {
  boardCount: number;
  agentCount: number;
  playerCount: number;
  gameCount: number;
}

interface AdminDashboardPageProps {
  stats: DashboardStats | null;
}

export function AdminDashboardPage({ stats }: AdminDashboardPageProps) {
  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="scene-kicker">CONTROL ROOM</p>
          <h2>配置工作台</h2>
        </div>
      </header>
      {stats ? (
        <div className="dashboard-grid">
          <div className="dashboard-card">
            <span className="dashboard-number">{stats.boardCount}</span>
            <span className="dashboard-label">板子</span>
          </div>
          <div className="dashboard-card">
            <span className="dashboard-number">{stats.agentCount}</span>
            <span className="dashboard-label">AI 人设</span>
          </div>
          <div className="dashboard-card">
            <span className="dashboard-number">{stats.playerCount}</span>
            <span className="dashboard-label">玩家</span>
          </div>
          <div className="dashboard-card">
            <span className="dashboard-number">{stats.gameCount}</span>
            <span className="dashboard-label">游戏记录</span>
          </div>
        </div>
      ) : (
        <div className="admin-metrics">
          <div>
            <span>流程</span>
            <strong>后台配置优先</strong>
          </div>
          <div>
            <span>范围</span>
            <strong>玩家 / AI / 板子</strong>
          </div>
          <div>
            <span>状态</span>
            <strong>MVP 可用</strong>
          </div>
        </div>
      )}
    </section>
  );
}
