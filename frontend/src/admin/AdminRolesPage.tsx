import type { AdminRoleDto } from "../types";

interface AdminRolesPageProps {
  roles: AdminRoleDto[];
  onSeed?: () => Promise<void>;
  onRefresh: () => void;
}

export function AdminRolesPage({ roles, onSeed, onRefresh }: AdminRolesPageProps) {
  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="scene-kicker">ROLES</p>
          <h2>角色元数据</h2>
        </div>
        <span className="admin-actions">
          <button className="ghost-action" type="button" onClick={onRefresh}>
            刷新
          </button>
          <button className="primary-action" type="button" disabled={!onSeed} onClick={() => void onSeed?.()}>
            初始化角色
          </button>
        </span>
      </header>
      <table className="admin-table">
        <thead>
          <tr>
            <th>Key</th>
            <th>名称</th>
            <th>阵营</th>
            <th>夜晚行动</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          {roles.map((role) => (
            <tr key={role.role_key}>
              <td>{role.role_key}</td>
              <td>{role.name}</td>
              <td>{role.faction}</td>
              <td>{role.night_action ? "是" : "否"}</td>
              <td>{role.description ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
