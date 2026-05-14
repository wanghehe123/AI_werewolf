export function AdminDashboardPage() {
  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="scene-kicker">CONTROL ROOM</p>
          <h2>配置工作台</h2>
        </div>
      </header>
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
    </section>
  );
}
