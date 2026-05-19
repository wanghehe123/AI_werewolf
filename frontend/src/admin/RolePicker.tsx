import type { AdminBoardRoleDto, AdminRoleDto } from "../types";

interface RolePickerProps {
  roles: AdminRoleDto[];
  value: AdminBoardRoleDto[];
  onChange: (roles: AdminBoardRoleDto[]) => void;
  minPlayers?: number;
  maxPlayers?: number;
}

const FACTION_LABELS: Record<string, string> = {
  wolf: "狼人阵营",
  good: "好人阵营",
  third: "第三方",
};

const FACTION_CLASS: Record<string, string> = {
  wolf: "faction-wolf",
  good: "faction-good",
  third: "faction-third",
};

export function RolePicker({ roles, value, onChange, minPlayers, maxPlayers }: RolePickerProps) {
  const total = value.reduce((sum, r) => sum + r.count, 0);
  const byFaction: Record<string, AdminRoleDto[]> = {};

  for (const role of roles) {
    const faction = role.faction || "unknown";
    if (!byFaction[faction]) byFaction[faction] = [];
    byFaction[faction].push(role);
  }

  function getCount(roleKey: string): number {
    return value.find((r) => r.role_key === roleKey)?.count ?? 0;
  }

  function handleChange(roleKey: string, delta: number) {
    const current = getCount(roleKey);
    const next = Math.max(0, current + delta);
    const other = value.filter((r) => r.role_key !== roleKey);
    onChange(next === 0 ? other : [...other, { role_key: roleKey, count: next }]);
  }

  return (
    <div className="role-picker">
      <div className="role-picker-header">
        <span className="role-picker-total">
          共 {total} 人{maxPlayers ? ` / ${maxPlayers}` : ""}
        </span>
        {minPlayers && total < minPlayers ? (
          <span className="role-picker-warning">至少需要 {minPlayers} 人</span>
        ) : null}
        {maxPlayers && total > maxPlayers ? (
          <span className="role-picker-warning">最多 {maxPlayers} 人</span>
        ) : null}
      </div>

      {Object.entries(byFaction).map(([faction, factionRoles]) => (
        <div key={faction} className={`role-picker-group ${FACTION_CLASS[faction] ?? ""}`}>
          <div className="role-picker-faction-header">{FACTION_LABELS[faction] ?? faction}</div>
          {factionRoles.map((role) => {
            const count = getCount(role.role_key);
            return (
              <div key={role.role_key} className="role-picker-item">
                <div className="role-picker-info">
                  <span className="role-picker-name">{role.name}</span>
                  {role.description ? <span className="role-picker-desc">{role.description}</span> : null}
                </div>
                <div className="role-picker-controls">
                  <button
                    className="role-picker-btn"
                    type="button"
                    aria-label={`减少 ${role.name}`}
                    disabled={count === 0}
                    onClick={() => handleChange(role.role_key, -1)}
                  >
                    −
                  </button>
                  <span className="role-picker-count">{count}</span>
                  <button
                    className="role-picker-btn"
                    type="button"
                    aria-label={`增加 ${role.name}`}
                    onClick={() => handleChange(role.role_key, 1)}
                  >
                    +
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
