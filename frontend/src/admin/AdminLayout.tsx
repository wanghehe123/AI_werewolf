import { NavLink, Outlet } from "react-router-dom";

interface AdminLayoutProps {
  logout?: () => Promise<void>;
}

const navItems = [
  ["/admin", "概览"],
  ["/admin/players", "玩家"],
  ["/admin/agents", "AI 人设"],
  ["/admin/boards", "板子"],
  ["/admin/roles", "角色"],
  ["/admin/llm", "模型"],
  ["/admin/games", "游戏记录"]
];

export function AdminLayout({ logout }: AdminLayoutProps) {
  return (
    <main className="admin-shell">
      <aside className="admin-sidebar">
        <div>
          <p className="scene-kicker">AI WEREWOLF</p>
          <h1>后台</h1>
        </div>
        <nav>
          {navItems.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/admin"}>
              {label}
            </NavLink>
          ))}
        </nav>
        {logout ? (
          <button className="ghost-action" type="button" onClick={() => void logout()}>
            登出
          </button>
        ) : null}
      </aside>
      <section className="admin-content">
        <Outlet />
      </section>
    </main>
  );
}
